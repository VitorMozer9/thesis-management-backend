from abc import ABC, abstractmethod

from thesis.domain.events.thesis_events import (ThesisCreatedEvent,)

class EventPublisherPort(ABC):

    @abstractmethod
    def publish(self,event: ThesisCreatedEvent) -> None:
        pass