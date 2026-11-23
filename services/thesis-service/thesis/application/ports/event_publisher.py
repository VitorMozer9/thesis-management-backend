from abc import ABC, abstractmethod

from thesis.domain.events.thesis_events import ThesisEvent

class EventPublisherPort(ABC):

    @abstractmethod
    def publish(self, event: ThesisEvent) -> None:
        pass