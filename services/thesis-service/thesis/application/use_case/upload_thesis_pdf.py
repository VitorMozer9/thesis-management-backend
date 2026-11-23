import logging

from dataclasses import dataclass
from hashlib import sha256
from typing import BinaryIO
from uuid import UUID, uuid4

from thesis.application.ports.unit_of_work import UnitOfWorkPort
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
    max_file_size_bytes: int = 20 * 1024 * 1024

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

            self.processing.set_status(
                thesis_id,
                UploadProcessingStatus.PROCESSING
            )

            try:
                content.seek(0)

                header = content.read(5)

                if header != b"%PDF-":
                    raise InvalidThesisError(
                        "File does not have a valid PDF signature."
                    )

                content.seek(0)

                file_hash = sha256()
                total_bytes = 0

                while chunk := content.read(1024 * 1024):

                    total_bytes += len(chunk)

                    if total_bytes > self.max_file_size_bytes:
                        raise InvalidThesisError(
                            "PDF exceeds the maximum allowed size."
                        )

                    file_hash.update(chunk)

                content.seek(0)

                file_key = (
                    f"theses/{thesis.id}/{uuid4().hex}.pdf"
                )

                saved_key = self.storage.save(
                    key=file_key,
                    content=content,
                )

                try:
                    updated_thesis = thesis.attach_file(
                        file_key=saved_key,
                        file_sha256=file_hash.hexdigest(),
                    )

                    with self.unit_of_work.transaction():
                        saved_thesis = self.repository.update_draft(updated_thesis, previous=thesis)
                        self.audit.record(self.actor, AuditAction.PDF_UPLOADED, thesis_id)

                except Exception:
                    self.storage.delete(saved_key)
                    raise

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
