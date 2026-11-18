from abc import ABC, abstractmethod
from enum import StrEnum
from uuid import UUID


class UploadProcessingStatus(StrEnum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UploadProcessingPort(ABC):

    @abstractmethod
    def set_status(
        self,
        thesis_id: UUID,
        status: UploadProcessingStatus
    ) -> None:
        pass

    @abstractmethod
    def get_status(
        self,
        thesis_id: UUID
    ) -> UploadProcessingStatus | None:
        pass