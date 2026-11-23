from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID

from thesis.domain.events.thesis_events import ThesisCreatedEvent


class OutboxDispatchPort(Protocol):

    def lock_next_pending(
        self,
    ) -> AbstractContextManager[ThesisCreatedEvent | None]:
        ...

    def register_attempt(self, event_id: UUID) -> None:
        ...

    def mark_published(self, event_id: UUID) -> None:
        ...