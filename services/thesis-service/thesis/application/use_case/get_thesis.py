from dataclasses import dataclass
from uuid import UUID

from thesis.domain.entities.thesis import Thesis

from thesis.application.ports.thesis_repository import ThesisRepository

from thesis.application.exceptions import ThesisNotFoundError


@dataclass
class GetThesisUseCase:

    repository: ThesisRepository

    def execute(self, thesis_id: UUID) -> Thesis:

        thesis = self.repository.find_by_id(thesis_id)

        if thesis is None:
            raise ThesisNotFoundError(
                f"Thesis {thesis_id} not found."
            )

        return thesis