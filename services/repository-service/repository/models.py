from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import models
from django.db.models import Q


class Entry(models.Model):
    thesis_id = models.UUIDField(primary_key=True)
    course_id = models.UUIDField(db_index=True)
    defense_id = models.UUIDField(unique=True, null=True)
    result = models.CharField(max_length=32, blank=True)
    defense_year = models.PositiveSmallIntegerField(null=True, db_index=True)
    reported_year = models.PositiveSmallIntegerField(null=True)
    title = models.CharField(max_length=255, blank=True)
    author = models.CharField(max_length=200, blank=True)
    advisor = models.CharField(max_length=200, blank=True, db_index=True)
    keywords = models.TextField(blank=True)
    final_hash = models.CharField(max_length=64, blank=True)
    term_hash = models.CharField(max_length=64, blank=True)
    corrected = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [
            models.Index(fields=["-published_at", "thesis_id"], condition=Q(published_at__isnull=False),
                         name="catalog_public_order"),
            *[GinIndex(SearchVector(field, config="simple"), name=f"catalog_{field}_fts",
                       condition=Q(published_at__isnull=False)) for field in ("title", "author", "keywords")],
        ]
        constraints = [
            models.CheckConstraint(name="catalog_public_requirements", condition=Q(published_at=None) | (
                Q(defense_id__isnull=False, defense_year__isnull=False)
                & (Q(result="approved") | Q(result="approved_with_conditions", corrected=True))
                & ~Q(final_hash="") & ~Q(term_hash="") & ~Q(title="") & ~Q(author="") & ~Q(advisor="") & ~Q(keywords="")
            )),
        ]


class Audit(models.Model):
    thesis_id = models.UUIDField(db_index=True)
    actor_id = models.UUIDField(null=True)
    event_id = models.UUIDField(null=True)
    action = models.CharField(max_length=40)
    occurred_at = models.DateTimeField(auto_now_add=True)


class Receipt(models.Model):
    event_id = models.UUIDField(primary_key=True)
    fingerprint = models.CharField(max_length=64)


class InvalidMessage(models.Model):
    topic = models.CharField(max_length=249)
    partition = models.IntegerField()
    offset = models.BigIntegerField()
    reason = models.CharField(max_length=80)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["topic", "partition", "offset"], name="catalog_invalid_offset")]


class CatalogRevision(models.Model):
    revision = models.UUIDField()
