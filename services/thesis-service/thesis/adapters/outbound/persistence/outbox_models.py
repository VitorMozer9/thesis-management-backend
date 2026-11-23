from uuid import uuid4

from django.db import models


class OutboxEventModel(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
    )

    event_type = models.CharField(
        max_length=120,
    )

    aggregate_id = models.UUIDField()

    payload = models.JSONField()

    occurred_at = models.DateTimeField()

    published_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    attempts = models.PositiveIntegerField(
        default=0,
    )

    class Meta:

        db_table = "outbox_events"

        indexes = [
            models.Index(
                fields=["published_at", "occurred_at"]
            ),
        ]