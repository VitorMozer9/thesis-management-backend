from abc import ABC, abstractmethod
from contextlib import AbstractContextManager


class UnitOfWorkPort(ABC):

    @abstractmethod
    def transaction(
        self,
    ) -> AbstractContextManager[None]:
        pass