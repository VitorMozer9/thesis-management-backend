from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from thesis.application.ports.outbox_dispatch import OutboxDispatchPort
from thesis.domain.events.thesis_events import ThesisCreatedEvent

from thesis.adapters.outbound.persistence.outbox_models import (
    OutboxEventModel,
)


class DjangoOutboxDispatchRepository(OutboxDispatchPort):

    @contextmanager
    def lock_next_pending(
        self,
    ) -> Iterator[ThesisCreatedEvent | None]:

        with transaction.atomic():

            record = (
                OutboxEventModel.objects
                .select_for_update(skip_locked=True)
                .filter(
                    published_at__isnull=True,
                    event_type=ThesisCreatedEvent.event_type,
                )
                .order_by("occurred_at", "id")
                .first()
            )

            if record is None:
                yield None
                return

            if record.payload.get("version") != ThesisCreatedEvent.version:
                raise ValueError(
                    f"Unsupported event version: {record.id}"
                )

            if record.payload.get("thesis_id") != str(record.aggregate_id):
                raise ValueError(
                    f"Invalid thesis_id in outbox event: {record.id}"
                )

            event = ThesisCreatedEvent(
                thesis_id=record.aggregate_id,
                event_id=record.id,
                occurred_at=record.occurred_at,
            )

            yield event

    def register_attempt(self, event_id: UUID) -> None:

        updated = OutboxEventModel.objects.filter(
            id=event_id,
            published_at__isnull=True,
        ).update(
            attempts=F("attempts") + 1,
        )

        if updated != 1:
            raise RuntimeError(
                f"Unable to register attempt for event {event_id}"
            )

    def mark_published(self, event_id: UUID) -> None:

        updated = OutboxEventModel.objects.filter(
            id=event_id,
            published_at__isnull=True,
        ).update(
            published_at=timezone.now(),
        )

        if updated != 1:
            raise RuntimeError(
                f"Unable to mark event {event_id} as published"
            )