from dataclasses import dataclass
from uuid import UUID

from thesis.domain.entities.thesis import Thesis

from thesis.domain.events.thesis_events import (
    ThesisCreatedEvent,
)

from thesis.application.ports.thesis_repository import (
    ThesisRepository,
)

from thesis.application.ports.outbox_repository import (
    OutboxRepositoryPort,
)

from thesis.application.ports.unit_of_work import (
    UnitOfWorkPort,
)


@dataclass
class CreateThesisUseCase:

    repository: ThesisRepository
    outbox_repository: OutboxRepositoryPort
    unit_of_work: UnitOfWorkPort

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

        with self.unit_of_work.transaction():

            saved_thesis = self.repository.save(thesis)

            event = ThesisCreatedEvent(
                thesis_id=saved_thesis.id
            )

            self.outbox_repository.add(event)

        return saved_thesis