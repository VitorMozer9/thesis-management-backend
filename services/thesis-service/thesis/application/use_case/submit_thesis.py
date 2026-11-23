from dataclasses import dataclass
from uuid import UUID

from thesis.application.exceptions import ThesisNotFoundError

from thesis.application.ports.thesis_repository import ThesisRepository
from thesis.application.ports.thesis_lock import ThesisLockPort
from thesis.application.ports.outbox_repository import OutboxRepositoryPort
from thesis.application.ports.unit_of_work import UnitOfWorkPort

from thesis.domain.entities.thesis import Thesis
from thesis.domain.events.thesis_events import ThesisSubmittedEvent


@dataclass
class SubmitThesisUseCase:

    repository: ThesisRepository
    thesis_lock: ThesisLockPort
    outbox_repository: OutboxRepositoryPort
    unit_of_work: UnitOfWorkPort

    def execute(self, thesis_id: UUID) -> Thesis:

        with self.thesis_lock.lock(thesis_id):

            with self.unit_of_work.transaction():

                thesis = self.repository.find_by_id(thesis_id)

                if thesis is None:
                    raise ThesisNotFoundError(
                        f"Thesis {thesis_id} not found."
                    )

                submitted_thesis = thesis.submit()

                saved_thesis = self.repository.save(
                    submitted_thesis
                )

                event = ThesisSubmittedEvent(
                    thesis_id=saved_thesis.id
                )

                self.outbox_repository.add(event)

                return saved_thesis