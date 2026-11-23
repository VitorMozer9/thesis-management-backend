from django.db import models
from django.utils import timezone

from thesis.adapters.outbound.persistence.models import ThesisModel
from thesis.application.ports.pdf_extraction import ExtractionStatus, PdfFailure, SubmissionFile
from thesis.domain.events.thesis_events import ThesisSubmittedEvent


class PdfExtractionModel(models.Model):
    thesis = models.OneToOneField(ThesisModel, primary_key=True, on_delete=models.CASCADE)
    event_id = models.UUIDField(unique=True)
    file_key = models.CharField(max_length=512)
    file_sha256 = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=[(state.value, state.name) for state in ExtractionStatus],
        default=ExtractionStatus.PENDING.value,
    )
    text = models.TextField(blank=True, default="")
    finished_at = models.DateTimeField(null=True)
    failure_code = models.CharField(max_length=32, blank=True, default="")

    class Meta:
        db_table = "thesis_pdf_extractions"


class DjangoExtractionRepository:

    def enqueue(self, event: ThesisSubmittedEvent, file: SubmissionFile) -> None:
        PdfExtractionModel.objects.create(
            event_id=event.event_id, thesis_id=event.thesis_id,
            file_key=file.key, file_sha256=file.sha256,
        )

    def mark_processing(self, event: ThesisSubmittedEvent) -> None:
        PdfExtractionModel.objects.filter(
            event_id=event.event_id, thesis_id=event.thesis_id, status=ExtractionStatus.PENDING,
        ).update(status=ExtractionStatus.PROCESSING)

    def lock_unfinished(self, event: ThesisSubmittedEvent) -> SubmissionFile | None:
        record = PdfExtractionModel.objects.select_for_update().defer("text").get(
            event_id=event.event_id, thesis_id=event.thesis_id,
        )
        if record.status in (ExtractionStatus.COMPLETED, ExtractionStatus.FAILED):
            return None

        if not ThesisModel.objects.filter(
            pk=event.thesis_id, file_key=record.file_key, file_sha256=record.file_sha256,
        ).exists():
            self.finish(event, "", PdfFailure.STALE)
            return None

        return SubmissionFile(record.file_key, record.file_sha256)

    def finish(self, event: ThesisSubmittedEvent, text: str, error: PdfFailure | None) -> None:
        record = PdfExtractionModel.objects.get(event_id=event.event_id, thesis_id=event.thesis_id)
        current = ThesisModel.objects.select_for_update().filter(
            pk=event.thesis_id, file_key=record.file_key, file_sha256=record.file_sha256,
        ).exists()
        if not current:
            error = PdfFailure.STALE

        record.status = ExtractionStatus.FAILED if error else ExtractionStatus.COMPLETED
        record.failure_code = error.value if error else ""
        record.text = "" if error else text
        record.finished_at = timezone.now()
        record.save(update_fields=["status", "failure_code", "text", "finished_at"])
