from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from uuid import UUID


class ThesisAlreadyLockedError(Exception):
    """Raised when another operation is modifying the thesis."""
    pass


class ThesisLockPort(ABC):

    @abstractmethod
    def lock(
        self,
        thesis_id: UUID
    ) -> AbstractContextManager[None]:
        pass