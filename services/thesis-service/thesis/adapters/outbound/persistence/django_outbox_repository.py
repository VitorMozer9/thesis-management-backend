from thesis.application.ports.outbox_repository import (
    OutboxRepositoryPort,
)

from thesis.domain.events.thesis_events import (
    ThesisCreatedEvent,
)

from thesis.adapters.outbound.persistence.outbox_models import (
    OutboxEventModel,
)


class DjangoOutboxRepository(OutboxRepositoryPort):

    def add(
        self,
        event: ThesisCreatedEvent,
    ) -> None:

        OutboxEventModel.objects.create(
            id=event.event_id,
            event_type=event.event_type,
            aggregate_id=event.thesis_id,
            payload={
                "version": event.version,
                "thesis_id": str(event.thesis_id),
            },
            occurred_at=event.occurred_at,
        )