from dataclasses import dataclass
from uuid import UUID

from thesis.application.exceptions import ThesisNotFoundError
from thesis.application.ports.thesis_repository import ThesisRepository
from thesis.application.ports.thesis_lock import ThesisLockPort

from thesis.domain.entities.thesis import Thesis
from thesis.domain.exceptions import InvalidThesisError


@dataclass
class UpdateThesisUseCase:

    repository: ThesisRepository
    thesis_lock: ThesisLockPort

    def execute(
        self,
        thesis_id: UUID,
        *,
        title: str | None = None,
        abstract: str | None = None,
        keywords: list[str] | tuple[str, ...] | None = None,
        advisor_id: UUID | None = None,
    ) -> Thesis:

        if all(
            value is None
            for value in (title, abstract, keywords, advisor_id)
        ):
            raise InvalidThesisError(
                "At least one field must be provided."
            )

        with self.thesis_lock.lock(thesis_id):

            thesis = self.repository.find_by_id(thesis_id)

            if thesis is None:
                raise ThesisNotFoundError(
                    f"Thesis {thesis_id} not found."
                )

            if title is not None:
                thesis = thesis.change_title(title)

            if abstract is not None:
                thesis = thesis.change_abstract(abstract)

            if keywords is not None:
                thesis = thesis.change_keywords(tuple(keywords))

            if advisor_id is not None:
                thesis = thesis.assign_advisor(advisor_id)

            return self.repository.update_draft(thesis)