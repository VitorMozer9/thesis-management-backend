from dataclasses import dataclass
from hashlib import sha256

from thesis.application.pdf_limits import MAX_PDF_BYTES
from thesis.application.ports.file_storage import FileStoragePort
from thesis.application.ports.pdf_extraction import (
    ExtractionRepository, InvalidPdf, PdfFailure, PdfTextExtractor, SubmissionFile,
)
from thesis.application.ports.unit_of_work import UnitOfWorkPort
from thesis.domain.events.thesis_events import ThesisSubmittedEvent


@dataclass
class ProcessSubmittedPdfUseCase:
    repository: ExtractionRepository
    storage: FileStoragePort
    extractor: PdfTextExtractor
    unit_of_work: UnitOfWorkPort
    max_bytes: int = MAX_PDF_BYTES

    def execute(self, event: ThesisSubmittedEvent) -> None:
        self.repository.mark_processing(event)

        with self.unit_of_work.transaction():
            file = self.repository.lock_unfinished(event)
            if file is None:
                return

            try:
                text = self.extract_verified(file)
            except InvalidPdf as exc:
                self.repository.finish(event, "", exc.reason)
            else:
                self.repository.finish(event, text, None)

    def extract_verified(self, file: SubmissionFile) -> str:
        with self.storage.open(file.key) as stream:
            content = stream.read(self.max_bytes + 1)

        if len(content) > self.max_bytes:
            raise InvalidPdf(PdfFailure.TOO_LARGE)
        if sha256(content).hexdigest() != file.sha256:
            raise InvalidPdf(PdfFailure.HASH_MISMATCH)

        return self.extractor.extract(content)
