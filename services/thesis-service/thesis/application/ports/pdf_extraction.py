from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from thesis.domain.events.thesis_events import ThesisSubmittedEvent


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PdfFailure(StrEnum):
    TOO_LARGE = "too_large"
    HASH_MISMATCH = "hash_mismatch"
    CORRUPT = "corrupt_pdf"
    ENCRYPTED = "encrypted_pdf"
    NO_TEXT = "no_text"
    PAGE_LIMIT = "page_limit"
    TEXT_LIMIT = "text_limit"
    TIME_LIMIT = "time_limit"
    STALE = "stale_file"


class InvalidPdf(Exception):
    def __init__(self, reason: PdfFailure):
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True)
class SubmissionFile:
    key: str
    sha256: str


class PdfTextExtractor(Protocol):
    def extract(self, content: bytes) -> str:
        ...


class ExtractionRepository(Protocol):
    def enqueue(self, event: ThesisSubmittedEvent, file: SubmissionFile) -> None:
        ...

    def mark_processing(self, event: ThesisSubmittedEvent) -> None:
        ...

    def lock_unfinished(self, event: ThesisSubmittedEvent) -> SubmissionFile | None:
        ...

    def finish(self, event: ThesisSubmittedEvent, text: str, error: PdfFailure | None) -> None:
        ...
