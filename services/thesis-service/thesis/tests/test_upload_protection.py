from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.test import TestCase
from redis.exceptions import ConnectionError as RedisConnectionError

from config import dependencies
from thesis.adapters.outbound.persistence.audit_models import ThesisAuditModel
from thesis.adapters.outbound.persistence.django_thesis_repository import DjangoThesisRepository
from thesis.adapters.outbound.persistence.outbox_models import OutboxEventModel
from thesis.adapters.outbound.redis.redis_rate_limit import RedisRateLimit
from thesis.adapters.outbound.redis.redis_thesis_lock import RedisThesisLockAdapter
from thesis.application.exceptions import ThesisNotFoundError
from thesis.application.identity import AcademicIdentity, Role
from thesis.application.ports.audit import AuditAction
from thesis.application.ports.thesis_lock import ThesisAlreadyLockedError
from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import ThesisNotEditableError
from thesis.tests.token_authority import TestTokenAuthority


PDF = b"%PDF-1.4\nconteudo original"
CHANGED_PDF = b"%PDF-1.4\nconteudo alterado"
UPLOAD_LOGGER = "thesis.application.use_case.upload_thesis_pdf"


class ProtectionFixture:

    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(self.settings(MEDIA_ROOT=str(self.root)))

        self.student = AcademicIdentity(uuid4(), Role.STUDENT, uuid4(), uuid4(), frozenset())
        self.redis = dependencies.get_redis_client()

        for operation in ("upload", "submit"):
            self.addCleanup(self.redis.delete, f"thesis:rate:{operation}:{self.student.account_id}")

    def create_draft(self, student=None, ready=False):
        student = student or self.student
        thesis = Thesis.create_draft("TCC", "Resumo", student.academic_id, student.course_id)

        if ready:
            key = f"theses/{thesis.id}/ready.pdf"
            self.write(key, PDF)
            thesis = (
                thesis.assign_advisor(uuid4())
                .change_keywords(("pesquisa",))
                .attach_file(key, sha256(PDF).hexdigest())
            )

        DjangoThesisRepository().save(thesis)

        return thesis

    def write(self, key, content):
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def upload(self, thesis_id, content=PDF, student=None):
        use_case = dependencies.build_upload_thesis_pdf_use_case(student or self.student)

        return use_case.execute(thesis_id, "tcc.pdf", len(content), BytesIO(content))

    def stored_files(self):
        return sorted(path.relative_to(self.root).as_posix() for path in self.root.rglob("*.pdf"))

    def find(self, thesis_id):
        return DjangoThesisRepository().find_by_id(thesis_id)


class RateLimitApiTests(ProtectionFixture, TestCase):

    def setUp(self):
        super().setUp()

        self.enterContext(self.settings(THESIS_UPLOAD_LIMIT=1, THESIS_SUBMIT_LIMIT=1))

        TestTokenAuthority(self).login(
            self.student.academic_id, self.student.course_id, sub=str(self.student.account_id)
        )

    def post_pdf(self, thesis_id, content=PDF, name="tcc.pdf"):
        uploaded = SimpleUploadedFile(name, content, content_type="application/pdf")

        return self.client.post(f"/api/theses/{thesis_id}/pdf/", data={"file": uploaded})

    def submit(self, thesis_id):
        return self.client.post(f"/api/theses/{thesis_id}/submit/")

    def test_upload_returns_429_after_quota(self):
        thesis = self.create_draft()

        self.assertEqual(self.post_pdf(thesis.id).status_code, 200)

        response = self.post_pdf(thesis.id, CHANGED_PDF)

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)
        self.assertEqual(self.find(thesis.id).file_sha256, sha256(PDF).hexdigest())
        self.assertEqual(len(self.stored_files()), 1)

    def test_invalid_uploads_do_not_consume_quota(self):
        thesis = self.create_draft()
        other_student_thesis = self.create_draft(
            AcademicIdentity(uuid4(), Role.STUDENT, uuid4(), uuid4(), frozenset())
        )

        self.assertEqual(self.post_pdf(thesis.id, b"not a pdf").status_code, 400)
        self.assertEqual(self.post_pdf(thesis.id, PDF, "tcc.txt").status_code, 400)
        self.assertEqual(self.post_pdf(other_student_thesis.id).status_code, 404)
        self.assertEqual(self.post_pdf(thesis.id).status_code, 200)

    def test_unauthenticated_requests_do_not_consume_quota(self):
        thesis = self.create_draft()
        self.client.defaults.pop("HTTP_AUTHORIZATION")

        self.assertEqual(self.post_pdf(thesis.id).status_code, 401)
        self.assertEqual(self.submit(thesis.id).status_code, 401)
        self.assertFalse(self.redis.exists(f"thesis:rate:upload:{self.student.account_id}"))
        self.assertFalse(self.redis.exists(f"thesis:rate:submit:{self.student.account_id}"))

    def test_quota_uses_token_subject_not_request_body(self):
        thesis = self.create_draft()

        response = self.client.post(
            f"/api/theses/{thesis.id}/pdf/",
            data={
                "file": SimpleUploadedFile("tcc.pdf", PDF, content_type="application/pdf"),
                "account_id": str(uuid4()),
                "sub": str(uuid4()),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.redis.get(f"thesis:rate:upload:{self.student.account_id}"), "1")

    def test_submit_returns_429_without_changing_state(self):
        first = self.create_draft(ready=True)
        second = self.create_draft(ready=True)

        self.assertEqual(self.submit(first.id).status_code, 200)

        response = self.submit(second.id)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.find(second.id).status, ThesisStatus.DRAFT)
        self.assertFalse(OutboxEventModel.objects.filter(aggregate_id=second.id).exists())
        self.assertFalse(
            ThesisAuditModel.objects.filter(thesis_id=second.id, action=AuditAction.SUBMITTED).exists()
        )

    def test_invalid_submission_does_not_consume_quota(self):
        incomplete = self.create_draft()
        ready = self.create_draft(ready=True)

        self.assertEqual(self.submit(incomplete.id).status_code, 400)
        self.assertEqual(self.submit(ready.id).status_code, 200)

    def test_redis_failure_blocks_upload_and_submit(self):
        draft = self.create_draft()
        ready = self.create_draft(ready=True)

        with patch.object(RedisRateLimit, "consume", side_effect=RedisConnectionError):
            upload = self.post_pdf(draft.id)
            submit = self.submit(ready.id)

        self.assertEqual(upload.status_code, 503)
        self.assertEqual(submit.status_code, 503)
        self.assertIsNone(self.find(draft.id).file_key)
        self.assertEqual(self.find(ready.id).status, ThesisStatus.DRAFT)
        self.assertEqual(self.stored_files(), [f"theses/{ready.id}/ready.pdf"])


class PdfDeduplicationTests(ProtectionFixture, TestCase):

    def setUp(self):
        super().setUp()

        self.enterContext(self.settings(THESIS_UPLOAD_LIMIT=100))

    def test_same_pdf_reuses_verified_file(self):
        thesis = self.create_draft()
        first = self.upload(thesis.id)
        second = self.upload(thesis.id)

        self.assertEqual(second.file_key, first.file_key)
        self.assertEqual(self.stored_files(), [first.file_key])
        self.assertEqual(
            ThesisAuditModel.objects.filter(thesis_id=thesis.id, action=AuditAction.PDF_UPLOADED).count(), 2
        )

    def test_changed_pdf_creates_new_file(self):
        thesis = self.create_draft()
        first = self.upload(thesis.id)
        second = self.upload(thesis.id, CHANGED_PDF)

        self.assertNotEqual(second.file_key, first.file_key)
        self.assertEqual(second.file_sha256, sha256(CHANGED_PDF).hexdigest())
        self.assertEqual((self.root / second.file_key).read_bytes(), CHANGED_PDF)

    def test_missing_stored_file_is_restored_under_new_key(self):
        thesis = self.create_draft()
        first = self.upload(thesis.id)
        (self.root / first.file_key).unlink()

        with self.assertLogs(UPLOAD_LOGGER, "WARNING"):
            second = self.upload(thesis.id)

        self.assertNotEqual(second.file_key, first.file_key)
        self.assertEqual((self.root / second.file_key).read_bytes(), PDF)

    def test_corrupted_stored_file_is_not_reused(self):
        thesis = self.create_draft()
        first = self.upload(thesis.id)
        (self.root / first.file_key).write_bytes(b"%PDF-adulterado")

        with self.assertLogs(UPLOAD_LOGGER, "WARNING"):
            second = self.upload(thesis.id)

        self.assertNotEqual(second.file_key, first.file_key)
        self.assertEqual(sha256((self.root / second.file_key).read_bytes()).hexdigest(), second.file_sha256)

    def test_same_content_is_not_shared_between_theses(self):
        first = self.upload(self.create_draft().id)
        second = self.upload(self.create_draft().id)

        self.assertNotEqual(first.file_key, second.file_key)
        self.assertEqual(len(self.stored_files()), 2)

    def test_database_failure_keeps_reference_and_files_consistent(self):
        thesis = self.create_draft()
        saved = self.upload(thesis.id)

        for content in (PDF, CHANGED_PDF):
            with self.subTest(content=content):
                with patch.object(DjangoThesisRepository, "update_draft", side_effect=DatabaseError):
                    with self.assertRaises(DatabaseError):
                        self.upload(thesis.id, content)

                self.assertEqual(self.find(thesis.id), saved)
                self.assertEqual(self.stored_files(), [saved.file_key])
                self.assertEqual((self.root / saved.file_key).read_bytes(), PDF)

    def test_concurrent_upload_is_rejected_without_consuming_quota(self):
        thesis = self.create_draft()
        lock = RedisThesisLockAdapter(self.redis)

        with lock.lock(thesis.id), self.assertRaises(ThesisAlreadyLockedError):
            self.upload(thesis.id)

        self.assertFalse(self.redis.exists(f"thesis:rate:upload:{self.student.account_id}"))
        self.assertEqual(self.stored_files(), [])

    def test_submitted_thesis_file_cannot_be_replaced(self):
        thesis = self.create_draft(ready=True)
        dependencies.build_submit_thesis_use_case(self.student).execute(thesis.id)

        with self.assertRaises(ThesisNotEditableError):
            self.upload(thesis.id, CHANGED_PDF)

        self.assertEqual(self.find(thesis.id).file_key, thesis.file_key)
        self.assertEqual(self.stored_files(), [thesis.file_key])

    def test_other_student_cannot_upload_to_thesis(self):
        thesis = self.create_draft()
        intruder = AcademicIdentity(uuid4(), Role.STUDENT, uuid4(), uuid4(), frozenset())
        self.addCleanup(self.redis.delete, f"thesis:rate:upload:{intruder.account_id}")

        with self.assertRaises(ThesisNotFoundError):
            self.upload(thesis.id, student=intruder)

        self.assertIsNone(self.find(thesis.id).file_key)
        self.assertEqual(self.stored_files(), [])
