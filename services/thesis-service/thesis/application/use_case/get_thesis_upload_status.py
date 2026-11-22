from dataclasses import dataclass
from uuid import UUID

from thesis.application.exceptions import ThesisNotFoundError

from thesis.application.ports.thesis_repository import (
    ThesisRepository,
)

from thesis.application.ports.upload_processing import (
    UploadProcessingPort,
    UploadProcessingStatus,
)


@dataclass
class GetThesisUploadStatusUseCase:

    repository: ThesisRepository
    processing: UploadProcessingPort

    def execute(self,thesis_id: UUID) -> UploadProcessingStatus | None:

        thesis = self.repository.find_by_id(thesis_id)

        if thesis is None:
            raise ThesisNotFoundError(f"Thesis {thesis_id} not found.")

        return self.processing.get_status(thesis_id)