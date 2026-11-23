from typing import Protocol
from uuid import UUID

from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus


class ThesisRepository(Protocol):

    def save(self, thesis: Thesis) -> Thesis:
        ...

    def find_by_id(self, thesis_id: UUID) -> Thesis | None:
        ...

    def find_by_id_for_update(self, thesis_id: UUID) -> Thesis | None:
        """Lock the thesis row until the current transaction ends."""
        ...

    def list(
        self,
        *,
        student_id: UUID | None,
        advisor_id: UUID | None,
        course_id: UUID | None,
        status: ThesisStatus | None,
        search: str | None,
        offset: int,
        limit: int,
    ) -> list[Thesis]:
        ...

    def update_draft(self, thesis: Thesis, *, previous: Thesis | None = None) -> Thesis:
        ...

    def delete(self, thesis_id: UUID) -> None:
        ...
