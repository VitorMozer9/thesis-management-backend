from abc import ABC, abstractmethod

from thesis.domain.events.thesis_events import ThesisEvent


class OutboxRepositoryPort(ABC):

    @abstractmethod
    def add(self, event: ThesisEvent) -> None:
        pass