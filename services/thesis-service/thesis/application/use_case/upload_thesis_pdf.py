from dataclasses import dataclass
from hashlib import sha256
from typing import BinaryIO
from uuid import UUID, uuid4

from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus

from thesis.domain.exceptions import (
    InvalidThesisError,
    ThesisNotEditableError,
)

from thesis.application.exceptions import ThesisNotFoundError

from thesis.application.ports.thesis_repository import ThesisRepository
from thesis.application.ports.file_storage import FileStoragePort


@dataclass
class UploadThesisPdfUseCase:

    repository: ThesisRepository
    storage: FileStoragePort

    max_file_size_bytes: int = 20 * 1024 * 1024

    def execute(
        self,
        thesis_id: UUID,
        filename: str,
        file_size: int,
        content: BinaryIO,
    ) -> Thesis:

        thesis = self.repository.find_by_id(thesis_id)

        if thesis is None:
            raise ThesisNotFoundError(
                f"Thesis {thesis_id} not found."
            )

        if thesis.status != ThesisStatus.DRAFT:
            raise ThesisNotEditableError(
                "Only draft theses can receive PDF uploads."
            )

        if not filename.lower().endswith(".pdf"):
            raise InvalidThesisError(
                "Only PDF files are allowed."
            )

        if file_size <= 0 or file_size > self.max_file_size_bytes:
            raise InvalidThesisError(
                "Invalid PDF file size."
            )

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

            return self.repository.save(updated_thesis)

        except Exception:
            self.storage.delete(saved_key)
            raise