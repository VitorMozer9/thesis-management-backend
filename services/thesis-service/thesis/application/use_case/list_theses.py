from dataclasses import dataclass
from uuid import UUID

from thesis.application.ports.thesis_repository import ThesisRepository
from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import InvalidThesisError

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_PAGE = 10000
MAX_SEARCH_LENGTH = 255


@dataclass
class ListThesesUseCase:

    repository: ThesisRepository

    def execute(
        self,
        *,
        student_id: UUID | None = None,
        advisor_id: UUID | None = None,
        course_id: UUID | None = None,
        status: ThesisStatus | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Thesis], bool]:
        """Return the requested page and whether another page exists."""
        if not 1 <= page <= MAX_PAGE:
            raise InvalidThesisError(f"Page must be between 1 and {MAX_PAGE}.")

        if not 1 <= page_size <= MAX_PAGE_SIZE:
            raise InvalidThesisError(
                f"Page size must be between 1 and {MAX_PAGE_SIZE}."
            )

        if search is not None:
            search = search.strip()
            if not search or len(search) > MAX_SEARCH_LENGTH or "\x00" in search:
                raise InvalidThesisError("Invalid thesis search term.")

        theses = self.repository.list(
            student_id=student_id,
            advisor_id=advisor_id,
            course_id=course_id,
            status=status,
            search=search,
            offset=(page - 1) * page_size,
            limit=page_size + 1,
        )

        return theses[:page_size], len(theses) > page_size and page < MAX_PAGE
