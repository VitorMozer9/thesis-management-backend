from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class Status(StrEnum):
    PROPOSED = "proposed"
    WAITING = "awaiting_confirmations"
    SCHEDULED = "scheduled"
    HELD = "held"
    CANCELLED = "cancelled"


class DefenseError(Exception):
    status = 409


class Forbidden(DefenseError):
    status = 403


class Missing(DefenseError):
    status = 404


class Unavailable(DefenseError):
    status = 503


@dataclass(frozen=True)
class Actor:
    account_id: UUID
    academic_id: UUID
    role: str
    course_id: UUID

    @property
    def is_authenticated(self):
        return True


@dataclass(frozen=True)
class Thesis:
    id: UUID
    course_id: UUID
    student_id: UUID
    advisor_id: UUID | None
    status: str


def calculate_result(evaluations):
    average = (sum(item.grade for item in evaluations) / len(evaluations)).quantize(Decimal("0.01"))
    choices = [item.recommendation for item in evaluations]
    if average < 7 or "rejected" in choices:
        return average, "rejected"
    return average, "approved_with_conditions" if "conditional" in choices else "approved"


@dataclass
class Defense:
    id: UUID
    thesis_id: UUID
    course_id: UUID
    student_id: UUID
    advisor_id: UUID
    status: Status
    starts_at: datetime | None
    ends_at: datetime | None
    venue: str
    meeting_url: str
    average: Decimal | None
    result: str
    created_at: datetime
    updated_at: datetime


@dataclass
class DefenseMember:
    id: UUID
    academic_id: UUID | None
    name: str
    email: str
    kind: str
    invite_status: str
    token_hash: str
    expires_at: datetime | None


@dataclass
class DefenseEvaluation:
    id: UUID
    member_id: UUID
    grade: Decimal
    opinion: str
    recommendation: str
    created_at: datetime
