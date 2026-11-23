import logging

from dataclasses import dataclass
from hashlib import sha256
from typing import BinaryIO
from uuid import UUID, uuid4

from thesis.application.pdf_limits import MAX_PDF_BYTES
from thesis.application.ports.unit_of_work import UnitOfWorkPort
from thesis.application.ports.rate_limit import RateLimitPort
from thesis.application.ports.audit import AuditAction, AuditPort
from thesis.application.identity import AcademicIdentity, Role
from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus

from thesis.domain.exceptions import (
    InvalidThesisError,
    ThesisNotEditableError,
)

from thesis.application.exceptions import ThesisNotFoundError

from thesis.application.ports.thesis_repository import ThesisRepository
from thesis.application.ports.file_storage import FileStoragePort
from thesis.application.ports.thesis_lock import ThesisLockPort

from thesis.application.ports.upload_processing import (
    UploadProcessingPort,
    UploadProcessingStatus,
)


logger = logging.getLogger(__name__)


@dataclass
class UploadThesisPdfUseCase:

    repository: ThesisRepository
    storage: FileStoragePort
    thesis_lock: ThesisLockPort
    processing: UploadProcessingPort

    unit_of_work: UnitOfWorkPort
    actor: AcademicIdentity
    audit: AuditPort
    rate_limit: RateLimitPort
    max_file_size_bytes: int = MAX_PDF_BYTES

    def execute(
        self,
        thesis_id: UUID,
        filename: str,
        file_size: int,
        content: BinaryIO,
    ) -> Thesis:

        self.actor.require_role(Role.STUDENT)

        if not filename.lower().endswith(".pdf"):
            raise InvalidThesisError(
                "Only PDF files are allowed."
            )

        if file_size <= 0 or file_size > self.max_file_size_bytes:
            raise InvalidThesisError(
                "Invalid PDF file size."
            )

        with self.thesis_lock.lock(thesis_id):

            thesis = self.repository.find_by_id(thesis_id)

            if thesis is None:
                raise ThesisNotFoundError(
                    f"Thesis {thesis_id} not found."
                )

            if thesis.status != ThesisStatus.DRAFT:
                raise ThesisNotEditableError(
                    "Only draft theses can receive PDF uploads."
                )

            content.seek(0)

            if content.read(5) != b"%PDF-":
                raise InvalidThesisError("File does not have a valid PDF signature.")

            content.seek(0)
            digest = self.hash_pdf(content)
            content.seek(0)

            self.rate_limit.consume(self.actor.account_id)

            self.processing.set_status(
                thesis_id,
                UploadProcessingStatus.PROCESSING
            )

            try:
                saved_thesis = self.store_pdf(thesis, digest, content)

            except Exception:

                try:
                    self.processing.set_status(
                        thesis_id,
                        UploadProcessingStatus.FAILED
                    )

                except Exception:
                    logger.exception(
                        "Could not register FAILED upload status."
                    )

                raise

            try:
                self.processing.set_status(
                    thesis_id,
                    UploadProcessingStatus.COMPLETED
                )

            except Exception:
                logger.exception(
                    "Could not register COMPLETED upload status."
                )

            return saved_thesis

    def hash_pdf(self, content: BinaryIO) -> str:
        digest = sha256()
        total_bytes = 0

        while chunk := content.read(1024 * 1024):
            total_bytes += len(chunk)

            if total_bytes > self.max_file_size_bytes:
                raise InvalidThesisError("PDF exceeds the maximum allowed size.")

            digest.update(chunk)

        return digest.hexdigest()

    def stored_copy_matches(self, thesis: Thesis, digest: str) -> bool:
        key = thesis.file_key

        if not key or thesis.file_sha256 != digest:
            return False

        if not key.startswith(f"theses/{thesis.id}/"):
            return False

        try:
            with self.storage.open(key) as stored:
                if self.hash_pdf(stored) == digest:
                    return True

        except (OSError, ValueError, InvalidThesisError):
            pass

        logger.warning("Stored PDF for thesis %s is missing or corrupted.", thesis.id)

        return False

    def store_pdf(self, thesis: Thesis, digest: str, content: BinaryIO) -> Thesis:
        reuse = self.stored_copy_matches(thesis, digest)
        key = thesis.file_key

        if not reuse:
            key = self.storage.save(f"theses/{thesis.id}/{uuid4().hex}.pdf", content)

        try:
            updated = thesis.attach_file(key, digest)

            with self.unit_of_work.transaction():
                saved = self.repository.update_draft(updated, previous=thesis)
                self.audit.record(self.actor, AuditAction.PDF_UPLOADED, thesis.id)

        except Exception:
            if not reuse:
                self.storage.delete(key)

            raise

        return saved
