from uuid import uuid4

from django.db import models
from django.utils import timezone


class Job(models.Model):
    status = models.CharField(max_length=7, default="pending")
    attempts = models.PositiveIntegerField(default=0)
    next_attempt = models.DateTimeField(default=timezone.now)
    error_code = models.CharField(max_length=40, blank=True)

    class Meta:
        abstract = True


class IncomingEvent(Job):
    id = models.UUIDField(primary_key=True)
    kind = models.CharField(max_length=40)
    aggregate_id = models.UUIDField()

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt"])]


class Notification(Job):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    event = models.ForeignKey(IncomingEvent, on_delete=models.PROTECT)
    recipient = models.CharField(max_length=254)
    academic_id = models.UUIDField(null=True)
    account_id = models.UUIDField(null=True)
    subject = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=["status", "next_attempt"]), models.Index(fields=["account_id", "-created_at"])]
        constraints = [models.UniqueConstraint(fields=["event", "recipient"], name="notification_event_recipient")]


class InvalidMessage(models.Model):
    topic = models.CharField(max_length=249)
    partition = models.IntegerField()
    offset = models.BigIntegerField()
    reason = models.CharField(max_length=40)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["topic", "partition", "offset"], name="notification_invalid_offset")]
