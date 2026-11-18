from typing import Protocol
from uuid import UUID

from thesis.domain.entities.thesis import Thesis


class ThesisRepository(Protocol):

    def save(self, thesis: Thesis) -> Thesis:
        ...

    def find_by_id(self, thesis_id: UUID) -> Thesis | None:
        ... 
        