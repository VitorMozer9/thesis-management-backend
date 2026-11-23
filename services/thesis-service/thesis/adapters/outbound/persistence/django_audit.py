from uuid import UUID

from thesis.adapters.outbound.persistence.audit_models import ThesisAuditModel
from thesis.application.identity import AcademicIdentity
from thesis.application.ports.audit import AuditAction, AuditPort


class DjangoAudit(AuditPort):

    def record(self, actor: AcademicIdentity, action: AuditAction, thesis_id: UUID) -> None:
        ThesisAuditModel.objects.create(
            account_id=actor.account_id,
            academic_id=actor.academic_id,
            role=actor.role.value,
            action=action.value,
            thesis_id=thesis_id,
        )
