import unittest

from uuid import uuid4

from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import (
    InvalidThesisError,
    ThesisNotEditableError,
    InvalidThesisStatusTransitionError,
    ThesisSubmissionError,
)


class ThesisTests(unittest.TestCase):

    def setUp(self):
        self.thesis = Thesis.create_draft(
            title="Distributed Systems",
            abstract="A study about distributed systems.",
            student_id=uuid4(),
            course_id=uuid4(),
        )

    def test_create_thesis_as_draft(self):
        self.assertEqual(
            self.thesis.status,
            ThesisStatus.DRAFT,
        )

    def test_create_thesis_without_title(self):
        with self.assertRaises(InvalidThesisError):
            Thesis.create_draft(
                title="",
                abstract="Test abstract",
                student_id=uuid4(),
                course_id=uuid4(),
            )

    def test_change_title_when_draft(self):
        updated = self.thesis.change_title(
            "Microservices Architecture"
        )

        self.assertEqual(
            updated.title,
            "Microservices Architecture",
        )

        self.assertEqual(
            self.thesis.title,
            "Distributed Systems",
        )

    def test_change_title_to_empty_value(self):
        with self.assertRaises(InvalidThesisError):
            self.thesis.change_title("")

    def test_draft_can_exist_without_pdf(self):
        self.assertIsNone(self.thesis.file_key)
        self.assertIsNone(self.thesis.file_sha256)

    def test_submit_without_pdf(self):
        with self.assertRaises(ThesisSubmissionError):
            self.thesis.submit()

    def test_submit_valid_thesis(self):
        updated = self.thesis.change_keywords(
            ("distributed systems", "microservices")
        )

        updated = updated.assign_advisor(uuid4())

        updated = updated.attach_file(
            "theses/document.pdf",
            "a" * 64,
        )

        submitted = updated.submit()

        self.assertEqual(
            submitted.status,
            ThesisStatus.SUBMITTED,
        )

    def test_cannot_edit_submitted_thesis(self):
        updated = self.thesis.change_keywords(
            ("distributed systems",)
        )

        updated = updated.assign_advisor(uuid4())

        updated = updated.attach_file(
            "theses/document.pdf",
            "a" * 64,
        )

        submitted = updated.submit()

        with self.assertRaises(ThesisNotEditableError):
            submitted.change_title("Another title")

    def test_cannot_submit_twice(self):
        updated = self.thesis.change_keywords(
            ("distributed systems",)
        )

        updated = updated.assign_advisor(uuid4())

        updated = updated.attach_file(
            "theses/document.pdf",
            "a" * 64,
        )

        submitted = updated.submit()

        with self.assertRaises(
            InvalidThesisStatusTransitionError
        ):
            submitted.submit()