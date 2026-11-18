from dataclasses import dataclass
from uuid import UUID

from thesis.domain.entities.thesis import Thesis

from thesis.application.ports.thesis_repository import ThesisRepository


@dataclass
class CreateThesisUseCase:

    repository: ThesisRepository

    def execute(
        self,
        title: str,
        abstract: str,
        student_id: UUID,
        course_id: UUID,
    ) -> Thesis:

        thesis = Thesis.create_draft(
            title=title,
            abstract=abstract,
            student_id=student_id,
            course_id=course_id,
        )

        return self.repository.save(thesis)