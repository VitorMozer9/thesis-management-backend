from uuid import uuid4

from django.db import models
from django.utils import timezone

from identity.application.ports import AccountAuditAction


class AccountAuditModel(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    actor_account_id = models.UUIDField(null=True, db_index=True)
    target_account_id = models.UUIDField(db_index=True)
    action = models.CharField(max_length=32, choices=[(action.value, action.value) for action in AccountAuditAction])
    changes = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    class Meta:
        db_table = "identity_account_audit"

        constraints = [
            models.CheckConstraint(
                condition=models.Q(action__in=[action.value for action in AccountAuditAction]),
                name="identity_account_audit_action_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Audit records are append-only.")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit records are append-only.")
