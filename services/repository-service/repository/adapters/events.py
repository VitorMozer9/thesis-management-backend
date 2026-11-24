import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from repository.domain import Conflict
from repository.models import InvalidMessage


@dataclass(frozen=True)
class Completion:
    event_id: UUID
    defense_id: UUID
    thesis_id: UUID
    course_id: UUID
    result: str
    year: int | None
    fingerprint: str


def decode(raw):
    if not raw or len(raw) > 65536:
        raise ValueError
    envelope = json.loads(raw)
    event_type = envelope["event_type"]
    event_id = UUID(envelope["event_id"])
    defense_id = UUID(envelope["aggregate_id"])
    if not isinstance(event_type, str) or not event_type or type(envelope["version"]) is not int:
        raise ValueError
    if not isinstance(envelope["data"], dict) or not datetime.fromisoformat(envelope["occurred_at"]).tzinfo:
        raise ValueError
    if event_type != "defense.completed":
        return None
    if envelope["version"] != 1:
        raise ValueError
    data = envelope["data"]
    year = data.get("defense_year")
    if year is not None and (type(year) is not int or not 1900 <= year <= 9999):
        raise ValueError
    if UUID(data["defense_id"]) != defense_id or data["result"] not in ("approved", "approved_with_conditions", "rejected"):
        raise ValueError
    fingerprint = hashlib.sha256(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return Completion(event_id, defense_id, UUID(data["thesis_id"]), UUID(data["course_id"]), data["result"], year, fingerprint)


def consume(message, consumer, service):
    reason = None
    try:
        event = decode(message.value())
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        reason = "invalid_envelope"
    else:
        if event:
            try:
                service.complete(event)
            except Conflict:
                reason = "inconsistent_completion"
    if reason:
        InvalidMessage.objects.get_or_create(topic=message.topic(), partition=message.partition(),
                                             offset=message.offset(), defaults={"reason": reason})
    consumer.commit(message=message, asynchronous=False)
    return reason
