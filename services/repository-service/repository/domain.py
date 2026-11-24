from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


class Conflict(Exception):
    pass


class Forbidden(Exception):
    pass


class Unavailable(Exception):
    pass


@dataclass(frozen=True)
class Actor:
    account_id: UUID
    academic_id: UUID
    role: str
    course_id: UUID

    @property
    def is_authenticated(self):
        return True


@dataclass
class Publication:
    thesis_id: UUID
    course_id: UUID
    defense_id: UUID | None
    result: str
    defense_year: int | None
    reported_year: int | None
    title: str
    author: str
    advisor: str
    keywords: str
    final_hash: str
    term_hash: str
    corrected: bool
    published_at: datetime | None

    def ready(self):
        return bool(
            self.defense_id and self.defense_year and self.reported_year in (None, self.defense_year)
            and self.title and self.author and self.advisor and self.keywords
            and self.final_hash and self.term_hash
            and (self.result == "approved" or self.result == "approved_with_conditions" and self.corrected)
        )
