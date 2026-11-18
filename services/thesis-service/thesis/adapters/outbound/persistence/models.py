from django.db import models

from thesis.domain.enums.thesis_status import ThesisStatus


class ThesisModel(models.Model):

    id = models.UUIDField(
        primary_key=True,
        editable=False,
    )

    title = models.CharField(max_length=255)

    abstract = models.TextField(blank=True)

    student_id = models.UUIDField(db_index=True)

    course_id = models.UUIDField(db_index=True)

    advisor_id = models.UUIDField(
        null=True,
        blank=True,
    )

    keywords = models.JSONField(default=list)

    file_key = models.CharField(
        max_length=512,
        null=True,
        blank=True,
    )

    file_sha256 = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=32,
        choices=[
            (status.value, status.name)
            for status in ThesisStatus
        ],
        default=ThesisStatus.DRAFT.value,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "theses"