from abc import ABC, abstractmethod

from thesis.domain.events.thesis_events import (
    ThesisCreatedEvent,
)


class OutboxRepositoryPort(ABC):

    @abstractmethod
    def add(
        self,
        event: ThesisCreatedEvent,
    ) -> None:
        pass