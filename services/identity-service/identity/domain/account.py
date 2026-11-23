from dataclasses import asdict, dataclass
from enum import StrEnum
from uuid import UUID, uuid4

from identity.domain.exceptions import AccountNotEligibleError, InvalidAccountError


MAX_NAME_LENGTH = 150

EDITABLE_FIELDS = frozenset({"name", "email", "role", "course_id"})


class Role(StrEnum):
    STUDENT = "student"
    ADVISOR = "advisor"
    COORDINATOR = "coordinator"
    ADMIN = "admin"


@dataclass(frozen=True)
class Account:
    id: UUID
    name: str
    email: str
    role: Role
    academic_id: UUID
    course_id: UUID | None
    is_active: bool

    @classmethod
    def provision(
        cls,
        *,
        name: str,
        email: str,
        role: Role,
        course_id: UUID | None,
        academic_id: UUID | None = None,
        is_active: bool = True,
    ) -> "Account":

        return cls.validated(
            id=uuid4(),
            name=name,
            email=email,
            role=role,
            academic_id=academic_id or uuid4(),
            course_id=course_id,
            is_active=is_active,
        )

    @classmethod
    def validated(cls, **fields) -> "Account":
        name = fields["name"].strip()

        try:
            role = Role(fields["role"])

        except ValueError as exc:
            raise InvalidAccountError("Unknown academic role.") from exc

        if not name or len(name) > MAX_NAME_LENGTH:
            raise InvalidAccountError("Name must have between 1 and 150 characters.")

        if role != Role.ADMIN and fields["course_id"] is None:
            raise InvalidAccountError("Academic roles other than admin require a course.")

        return cls(**{**fields, "name": name, "email": fields["email"].strip().lower(), "role": role})

    def change(self, **changes) -> "Account":
        unknown = changes.keys() - EDITABLE_FIELDS

        if unknown:
            raise InvalidAccountError("Fields cannot be changed: " + ", ".join(sorted(unknown)))

        return Account.validated(**{**asdict(self), **changes})

    def token_course(self) -> UUID:
        if not self.is_active:
            raise AccountNotEligibleError("Account is inactive.")

        if self.course_id is None:
            raise AccountNotEligibleError("Account is not linked to an academic course.")

        return self.course_id
