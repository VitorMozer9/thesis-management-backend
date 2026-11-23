from uuid import uuid4

from django.db import models
from django.db.models import F, Q


class Defense(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    thesis_id = models.UUIDField()
    course_id = models.UUIDField(db_index=True)
    student_id = models.UUIDField()
    advisor_id = models.UUIDField()
    status = models.CharField(max_length=24, default="proposed")
    starts_at = models.DateTimeField(null=True)
    ends_at = models.DateTimeField(null=True)
    venue = models.CharField(max_length=255, blank=True)
    meeting_url = models.URLField(max_length=500, blank=True)
    average = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    result = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["thesis_id"], condition=~Q(status="cancelled"), name="unique_active_defense"),
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")) | Q(starts_at__isnull=True, ends_at__isnull=True), name="defense_interval"),
        ]
        indexes = [models.Index(fields=["status", "starts_at", "ends_at"])]


class Member(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    defense = models.ForeignKey(Defense, on_delete=models.CASCADE, related_name="members")
    academic_id = models.UUIDField(null=True)
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    kind = models.CharField(max_length=8)
    invite_status = models.CharField(max_length=12, default="pending")
    token_hash = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["defense", "academic_id"], name="unique_internal_member"),
            models.UniqueConstraint(fields=["defense", "email"], condition=Q(kind="external"), name="unique_external_member"),
            models.CheckConstraint(condition=Q(kind="internal", academic_id__isnull=False, email="") | (Q(kind="external", academic_id__isnull=True) & ~Q(email="") & ~Q(name="")), name="member_identity"),
        ]
        indexes = [models.Index(fields=["academic_id"]), models.Index(fields=["email"])]


class Evaluation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    member = models.OneToOneField(Member, on_delete=models.CASCADE)
    grade = models.DecimalField(max_digits=4, decimal_places=2)
    opinion = models.TextField()
    recommendation = models.CharField(max_length=12)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(grade__gte=0, grade__lte=10), name="evaluation_grade")]


class Audit(models.Model):
    defense_id = models.UUIDField(db_index=True)
    actor_id = models.UUIDField()
    action = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)


class Outbox(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    defense_id = models.UUIDField()
    event_type = models.CharField(max_length=50)
    data = models.JSONField()
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["published_at", "occurred_at"])]
