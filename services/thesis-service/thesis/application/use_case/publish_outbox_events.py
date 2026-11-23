from dataclasses import dataclass

from thesis.application.exceptions import EventPublicationError

from thesis.application.ports.event_publisher import EventPublisherPort
from thesis.application.ports.outbox_dispatch import OutboxDispatchPort


@dataclass(frozen=True)
class PublishOutboxResult:

    published: int
    failed: int


@dataclass
class PublishOutboxEventsUseCase:

    repository: OutboxDispatchPort
    publisher: EventPublisherPort

    def execute(self, limit: int = 20) -> PublishOutboxResult:

        if limit < 1:
            raise ValueError("Limit must be greater than zero.")

        published = 0
        failed = 0

        for _ in range(limit):

            with self.repository.lock_next_pending() as event:

                if event is None:
                    break

                try:
                    self.publisher.publish(event)

                except EventPublicationError:

                    self.repository.register_attempt(event.event_id)

                    failed += 1
                    break

                self.repository.register_attempt(event.event_id)
                self.repository.mark_published(event.event_id)

                published += 1

        return PublishOutboxResult(
            published=published,
            failed=failed,
        )