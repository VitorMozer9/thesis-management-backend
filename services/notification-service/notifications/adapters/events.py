import json
from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.db import transaction

from notifications.domain import MESSAGES
from notifications.models import IncomingEvent, InvalidMessage


def decode(topic, raw):
    if not raw or len(raw) > 65536:
        raise ValueError
    envelope = json.loads(raw)
    kind = envelope["event_type"]
    if not isinstance(kind, str):
        raise ValueError
    if kind not in MESSAGES:
        return None
    if type(envelope["version"]) is not int or envelope["version"] != 1:
        raise ValueError
    if topic != settings.TOPICS[kind.split(".")[0]]:
        raise ValueError
    if datetime.fromisoformat(envelope["occurred_at"]).utcoffset() is None:
        raise ValueError

    aggregate = UUID(envelope["aggregate_id"])
    key = "defense_id" if kind.startswith("defense.") else "thesis_id"
    if UUID(envelope["data"][key]) != aggregate:
        raise ValueError
    return UUID(envelope["event_id"]), kind, aggregate


def consume(consumer, message):
    position = {"topic": message.topic(), "partition": message.partition(), "offset": message.offset()}
    with transaction.atomic():
        try:
            parsed = decode(position["topic"], message.value())
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            InvalidMessage.objects.get_or_create(**position, defaults={"reason": "invalid_envelope"})
        else:
            if parsed:
                event_id, kind, aggregate = parsed
                row, _ = IncomingEvent.objects.get_or_create(pk=event_id, defaults={"kind": kind, "aggregate_id": aggregate})
                if (row.kind, row.aggregate_id) != (kind, aggregate):
                    InvalidMessage.objects.get_or_create(**position, defaults={"reason": "event_id_conflict"})
    offsets = consumer.commit(message=message, asynchronous=False)
    if any(offset.error for offset in offsets or []):
        raise RuntimeError("Falha na confirmação do offset.")
