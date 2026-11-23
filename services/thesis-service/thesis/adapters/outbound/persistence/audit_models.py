from uuid import uuid4

from django.db import models


class ThesisAuditModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    account_id = models.UUIDField()
    academic_id = models.UUIDField()
    role = models.CharField(max_length=16)
    action = models.CharField(max_length=32)
    thesis_id = models.UUIDField(db_index=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "thesis_audit"
        default_permissions = ()
