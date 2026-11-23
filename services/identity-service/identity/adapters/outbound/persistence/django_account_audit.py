from identity.adapters.outbound.persistence.audit_models import AccountAuditModel
from identity.application.ports import AccountAuditEntry


class DjangoAccountAudit:

    def record(self, entry: AccountAuditEntry) -> None:
        AccountAuditModel.objects.create(
            actor_account_id=entry.actor_id,
            target_account_id=entry.target_id,
            action=entry.action.value,
            changes=entry.changes,
        )
