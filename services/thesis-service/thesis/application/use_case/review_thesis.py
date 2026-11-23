from dataclasses import dataclass
from uuid import UUID

from thesis.application.exceptions import ThesisAdvisorPermissionError, ThesisNotFoundError
from thesis.application.ports.outbox_repository import OutboxRepositoryPort
from thesis.application.ports.thesis_lock import ThesisLockPort
from thesis.application.ports.thesis_repository import ThesisRepository
from thesis.application.ports.unit_of_work import UnitOfWorkPort
from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.events.thesis_events import ThesisAdvisorApprovedEvent, ThesisAdvisorRejectedEvent


@dataclass
class ReviewThesisUseCase:
    repository: ThesisRepository
    thesis_lock: ThesisLockPort
    outbox_repository: OutboxRepositoryPort
    unit_of_work: UnitOfWorkPort

    def execute(
        self, thesis_id: UUID, *, authenticated_advisor_id: UUID, decision: ThesisStatus
    ) -> Thesis:
        """The caller must obtain the advisor UUID from a trusted identity source."""
        with self.thesis_lock.lock(thesis_id), self.unit_of_work.transaction():
            thesis = self.repository.find_by_id_for_update(thesis_id)
            if thesis is None:
                raise ThesisNotFoundError(f"Thesis {thesis_id} not found.")
            if thesis.advisor_id is None or thesis.advisor_id != authenticated_advisor_id:
                raise ThesisAdvisorPermissionError("Only the assigned advisor can review this thesis.")

            reviewed = self.repository.save(thesis.review_by_advisor(decision))
            event_type = (
                ThesisAdvisorApprovedEvent
                if decision == ThesisStatus.ADVISOR_APPROVED
                else ThesisAdvisorRejectedEvent
            )
            self.outbox_repository.add(event_type(thesis_id=reviewed.id))
            return reviewed
