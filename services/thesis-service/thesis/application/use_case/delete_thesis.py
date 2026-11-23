from dataclasses import dataclass
from uuid import UUID

from thesis.application.exceptions import ThesisNotFoundError
from thesis.application.ports.thesis_lock import ThesisLockPort
from thesis.application.ports.thesis_repository import ThesisRepository
from thesis.application.ports.unit_of_work import UnitOfWorkPort
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import InvalidThesisStatusTransitionError


@dataclass
class DeleteThesisUseCase:

    repository: ThesisRepository
    thesis_lock: ThesisLockPort
    unit_of_work: UnitOfWorkPort

    def execute(self, thesis_id: UUID) -> None:
        """Delete a draft while retaining its PDF and Outbox history."""
        with self.thesis_lock.lock(thesis_id), self.unit_of_work.transaction():
            thesis = self.repository.find_by_id_for_update(thesis_id)

            if thesis is None:
                raise ThesisNotFoundError(f"Thesis {thesis_id} not found.")

            if thesis.status != ThesisStatus.DRAFT:
                raise InvalidThesisStatusTransitionError(
                    "Only draft theses can be deleted."
                )

            self.repository.delete(thesis_id)
