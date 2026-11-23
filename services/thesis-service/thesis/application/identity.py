from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    STUDENT = "student"
    ADVISOR = "advisor"
    COORDINATOR = "coordinator"
    ADMIN = "admin"


class ThesisAccessDenied(Exception):
    """The verified identity does not grant this operation."""


@dataclass(frozen=True)
class AcademicIdentity:
    account_id: UUID
    role: Role
    academic_id: UUID
    course_id: UUID
    assignable_advisors: frozenset[UUID]

    @property
    def is_authenticated(self) -> bool:
        return True

    def scope(self) -> dict[str, UUID]:
        filters = {"course_id": self.course_id}
        if self.role == Role.STUDENT:
            filters["student_id"] = self.academic_id
        elif self.role == Role.ADVISOR:
            filters["advisor_id"] = self.academic_id

        return filters

    def require_role(self, role: Role) -> None:
        if self.role != role:
            raise ThesisAccessDenied("Operation not permitted for this role.")

    def authorize_creation(self, student_id: UUID, course_id: UUID) -> None:
        self.require_role(Role.STUDENT)
        if student_id != self.academic_id or course_id != self.course_id:
            raise ThesisAccessDenied("Student or course outside the authorized scope.")

    def authorize_patch(self, *, advisor_id: UUID | None, edits_metadata: bool) -> None:
        if advisor_id is None:
            self.require_role(Role.STUDENT)
            return

        self.require_role(Role.COORDINATOR)
        if edits_metadata or advisor_id not in self.assignable_advisors:
            raise ThesisAccessDenied("Advisor assignment outside the authorized scope.")
