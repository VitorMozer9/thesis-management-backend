from enum import StrEnum
from typing import Protocol
from uuid import UUID

from thesis.application.identity import AcademicIdentity


class AuditAction(StrEnum):
    CREATED = "thesis.created"
    METADATA_UPDATED = "thesis.metadata_updated"
    ADVISOR_ASSIGNED = "thesis.advisor_assigned"
    PDF_UPLOADED = "thesis.pdf_uploaded"
    SUBMITTED = "thesis.submitted"
    ADVISOR_APPROVED = "thesis.advisor_approved"
    ADVISOR_REJECTED = "thesis.advisor_rejected"
    DELETED = "thesis.deleted"


class AuditPort(Protocol):

    def record(self, actor: AcademicIdentity, action: AuditAction, thesis_id: UUID) -> None:
        ...
