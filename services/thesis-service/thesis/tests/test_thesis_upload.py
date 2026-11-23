from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from thesis.tests.token_authority import TestTokenAuthority

from django.test import TestCase, override_settings

from thesis.domain.entities.thesis import Thesis
from thesis.adapters.outbound.persistence.models import ThesisModel
from thesis.adapters.outbound.persistence.django_thesis_repository import (
    DjangoThesisRepository,
)


class ThesisUploadTests(TestCase):

    def setUp(self):
        self.temporary_directory = TemporaryDirectory()

        self.addCleanup(
            self.temporary_directory.cleanup
        )

        settings_override = override_settings(
            MEDIA_ROOT=self.temporary_directory.name
        )

        settings_override.enable()

        self.addCleanup(settings_override.disable)

        self.thesis = Thesis.create_draft(
            title="Distributed Systems",
            abstract="A study about distributed systems.",
            student_id=uuid4(),
            course_id=uuid4(),
        )

        DjangoThesisRepository().save(self.thesis)

        TestTokenAuthority(self).login(self.thesis.student_id, self.thesis.course_id)

    def test_upload_pdf(self):
        content = b"%PDF-1.4\nTest PDF content"

        uploaded_file = SimpleUploadedFile(
            "thesis.pdf",
            content,
            content_type="application/pdf",
        )

        response = self.client.post(
            f"/api/theses/{self.thesis.id}/pdf/",
            data={"file": uploaded_file},
        )

        self.assertEqual(response.status_code, 200)

        model = ThesisModel.objects.get(
            id=self.thesis.id
        )

        self.assertEqual(
            model.file_sha256,
            sha256(content).hexdigest(),
        )

        self.assertIsNotNone(model.file_key)

        stored_file = (
            Path(self.temporary_directory.name)
            / model.file_key
        )

        self.assertTrue(stored_file.exists())

    def test_reject_non_pdf(self):
        uploaded_file = SimpleUploadedFile(
            "document.txt",
            b"This is not a PDF",
            content_type="text/plain",
        )

        response = self.client.post(
            f"/api/theses/{self.thesis.id}/pdf/",
            data={"file": uploaded_file},
        )

        self.assertEqual(response.status_code, 400)