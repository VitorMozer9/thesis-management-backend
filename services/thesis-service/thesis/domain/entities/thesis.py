from dataclasses import dataclass, field, replace
from uuid import UUID, uuid4

from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import (
    InvalidThesisError,
    ThesisNotEditableError,
    InvalidThesisStatusTransitionError,
    ThesisSubmissionError,
)

@dataclass(frozen=True, kw_only=True)
class Thesis:
    title: str
    abstract: str
    student_id: UUID
    course_id: UUID

    id: UUID = field(default_factory=uuid4)
    advisor_id: UUID | None = None

    keywords: tuple[str, ...] = ()

    file_key: str | None = None
    file_sha256: str | None = None

    status: ThesisStatus = ThesisStatus.DRAFT

    def __post_init__(self):
        if not isinstance(self.title, str) or not self.title.strip():
            raise InvalidThesisError(
                "Thesis title cannot be empty."
            )

        if not isinstance(self.abstract, str):
            raise InvalidThesisError(
                "Thesis abstract must be a string."
            )

        if not isinstance(self.student_id, UUID):
            raise InvalidThesisError(
                "Student ID must be a UUID."
            )

        if not isinstance(self.course_id, UUID):
            raise InvalidThesisError(
                "Course ID must be a UUID."
            )

        if self.advisor_id is not None and not isinstance(
            self.advisor_id, UUID
        ):
            raise InvalidThesisError(
                "Advisor ID must be a UUID."
            )

        if not isinstance(self.keywords, tuple) or any(
            not isinstance(keyword, str) or not keyword.strip()
            for keyword in self.keywords
        ):
            raise InvalidThesisError(
                "Keywords must be a tuple of non-empty strings."
            )

        if not isinstance(self.status, ThesisStatus):
            raise InvalidThesisError(
                "Invalid thesis status."
            )

        if (self.file_key is None) != (self.file_sha256 is None):
            raise InvalidThesisError(
                "File key and SHA-256 must be provided together."
            )

        if self.file_key is not None:
            if (
                not isinstance(self.file_key, str)
                or not self.file_key.strip()
            ):
                raise InvalidThesisError(
                    "File key cannot be empty."
                )

            if (
                not isinstance(self.file_sha256, str)
                or len(self.file_sha256) != 64
                or any(
                    char not in "0123456789abcdefABCDEF"
                    for char in self.file_sha256
                )
            ):
                raise InvalidThesisError(
                    "Invalid SHA-256 hash."
                )

    @classmethod
    def create_draft(
        cls,
        title: str,
        abstract: str,
        student_id: UUID,
        course_id: UUID,
    ) -> "Thesis":
        return cls(
            title=title,
            abstract=abstract,
            student_id=student_id,
            course_id=course_id,
            status=ThesisStatus.DRAFT,
        )

    def _ensure_editable(self) -> None:
        if self.status != ThesisStatus.DRAFT:
            raise ThesisNotEditableError(
                "Only draft theses can be edited."
            )

    def change_title(self, new_title: str) -> "Thesis":
        self._ensure_editable()

        return replace(
            self,
            title=new_title,
        )

    def change_abstract(self, new_abstract: str) -> "Thesis":
        self._ensure_editable()

        return replace(
            self,
            abstract=new_abstract,
        )

    def change_keywords(
        self,
        new_keywords: tuple[str, ...],
    ) -> "Thesis":
        self._ensure_editable()

        return replace(
            self,
            keywords=new_keywords,
        )

    def assign_advisor(self, advisor_id: UUID) -> "Thesis":
        self._ensure_editable()

        return replace(
            self,
            advisor_id=advisor_id,
        )

    def attach_file(
        self,
        file_key: str,
        file_sha256: str,
    ) -> "Thesis":
        self._ensure_editable()

        return replace(
            self,
            file_key=file_key,
            file_sha256=file_sha256,
        )

    def submit(self) -> "Thesis":
        if self.status != ThesisStatus.DRAFT:
            raise InvalidThesisStatusTransitionError(
                "Only draft theses can be submitted."
            )

        if not self.abstract.strip():
            raise ThesisSubmissionError(
                "Abstract is required for submission."
            )

        if not self.keywords:
            raise ThesisSubmissionError(
                "Keywords are required for submission."
            )

        if self.advisor_id is None:
            raise ThesisSubmissionError(
                "An advisor must be assigned."
            )

        if self.file_key is None or self.file_sha256 is None:
            raise ThesisSubmissionError(
                "A PDF must be attached before submission."
            )

        return replace(
            self,
            status=ThesisStatus.SUBMITTED,
        )