from dataclasses import dataclass
from uuid import UUID

from thesis.domain.entities.thesis import Thesis

from thesis.application.ports.thesis_repository import ThesisRepository

from thesis.application.exceptions import ThesisNotFoundError

from thesis.domain.exceptions import InvalidThesisError


@dataclass
class UpdateThesisUseCase:

    repository: ThesisRepository

    def execute(
        self,
        thesis_id: UUID,
        *,
        title: str | None = None,
        abstract: str | None = None,
        keywords: tuple[str, ...] | None = None,
    ) -> Thesis:

        if (
            title is None
            and abstract is None
            and keywords is None
        ):
            raise InvalidThesisError(
                "At least one field must be provided."
            )

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
            thesis = thesis.change_keywords(keywords)

        return self.repository.save(thesis)