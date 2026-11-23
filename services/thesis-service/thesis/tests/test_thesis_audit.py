from datetime import timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase

from config import dependencies
from thesis.adapters.outbound.persistence.audit_models import ThesisAuditModel
from thesis.adapters.outbound.persistence.outbox_models import OutboxEventModel
from thesis.application.identity import AcademicIdentity, Role, ThesisAccessDenied
from thesis.application.ports.audit import AuditAction
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import InvalidThesisError
from thesis.tests.token_authority import TestTokenAuthority


class ThesisAuditTests(TestCase):

    def setUp(self):
        course = uuid4()
        self.student = AcademicIdentity(uuid4(), Role.STUDENT, uuid4(), course, frozenset())
        self.advisor = AcademicIdentity(uuid4(), Role.ADVISOR, uuid4(), course, frozenset())
        self.coordinator = AcademicIdentity(
            uuid4(), Role.COORDINATOR, uuid4(), course, frozenset({self.advisor.academic_id})
        )
        self.directory = self.enterContext(TemporaryDirectory())
        self.enterContext(self.settings(MEDIA_ROOT=self.directory))
        self.create = dependencies.build_create_thesis_use_case(self.student)

    def create_draft(self):
        return self.create.execute(
            "Título", "Resumo", self.student.academic_id, self.student.course_id
        )

    def upload(self, use_case, thesis_id):
        pdf = b"%PDF-test"
        return use_case.execute(thesis_id, "sample.pdf", len(pdf), BytesIO(pdf))

    def test_records_each_transition_and_verified_actor(self):
        for decision, action in (
            (ThesisStatus.ADVISOR_APPROVED, AuditAction.ADVISOR_APPROVED),
            (ThesisStatus.ADVISOR_REJECTED, AuditAction.ADVISOR_REJECTED),
        ):
            with self.subTest(decision=decision):
                thesis = self.create_draft()
                dependencies.build_update_thesis_use_case(self.student).execute(
                    thesis.id, keywords=("audit",)
                )
                dependencies.build_update_thesis_use_case(self.coordinator).execute(
                    thesis.id, advisor_id=self.advisor.academic_id
                )
                self.upload(dependencies.build_upload_thesis_pdf_use_case(self.student), thesis.id)
                dependencies.build_submit_thesis_use_case(self.student).execute(thesis.id)
                dependencies.build_review_thesis_use_case(self.advisor).execute(
                    thesis.id, authenticated_advisor_id=self.advisor.academic_id, decision=decision
                )

                expected = (
                    (AuditAction.CREATED, self.student),
                    (AuditAction.METADATA_UPDATED, self.student),
                    (AuditAction.ADVISOR_ASSIGNED, self.coordinator),
                    (AuditAction.PDF_UPLOADED, self.student),
                    (AuditAction.SUBMITTED, self.student),
                    (action, self.advisor),
                )
                records = ThesisAuditModel.objects.filter(thesis_id=thesis.id)
                self.assertCountEqual(
                    records.values_list("action", "account_id", "academic_id", "role"),
                    [(act.value, user.account_id, user.academic_id, user.role.value) for act, user in expected],
                )
                for record in records:
                    self.assertEqual(record.occurred_at.utcoffset(), timedelta(0))

    def test_deletion_preserves_both_records(self):
        thesis = self.create_draft()
        dependencies.build_delete_thesis_use_case(self.student).execute(thesis.id)

        self.assertIsNone(self.create.repository.find_by_id(thesis.id))
        records = ThesisAuditModel.objects.filter(thesis_id=thesis.id)
        self.assertCountEqual(records.values_list("action", flat=True), [AuditAction.CREATED, AuditAction.DELETED])
        deleted = records.get(action=AuditAction.DELETED)
        self.assertEqual(deleted.account_id, self.student.account_id)

    def test_denied_changes_leave_no_success_record(self):
        thesis = self.create_draft()
        update = dependencies.build_update_thesis_use_case(self.student)

        with self.assertRaises(ThesisAccessDenied):
            update.execute(thesis.id, advisor_id=self.advisor.academic_id)

        with self.assertRaises(InvalidThesisError):
            update.execute(thesis.id, title="")

        self.assertEqual(ThesisAuditModel.objects.count(), 1)
        self.assertEqual(self.create.repository.find_by_id(thesis.id), thesis)

    def test_create_rolls_back_thesis_outbox_and_audit(self):
        record = self.create.audit.record

        def fail_after_insert(*args):
            record(*args)
            raise RuntimeError("Falha após inserir a auditoria")

        with patch.object(self.create.audit, "record", side_effect=fail_after_insert):
            with self.assertRaises(RuntimeError):
                self.create_draft()

        self.assertFalse(self.create.repository.records.exists())
        self.assertFalse(OutboxEventModel.objects.exists())
        self.assertFalse(ThesisAuditModel.objects.exists())

    def test_upload_audit_failure_restores_pdf_reference_and_removes_new_file(self):
        thesis = self.create_draft()
        upload = dependencies.build_upload_thesis_pdf_use_case(self.student)
        saved = self.upload(upload, thesis.id)

        with patch.object(upload.audit, "record", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.upload(upload, thesis.id)

        self.assertEqual(self.create.repository.find_by_id(thesis.id), saved)
        self.assertEqual(list(Path(self.directory).rglob("*.pdf")), [Path(self.directory) / saved.file_key])
        self.assertEqual(ThesisAuditModel.objects.filter(action=AuditAction.PDF_UPLOADED).count(), 1)

    def test_http_creation_uses_signed_identity_for_audit(self):
        TestTokenAuthority(self).login(
            self.student.academic_id, self.student.course_id, sub=str(self.student.account_id)
        )
        response = self.client.post(
            "/api/theses/",
            {
                "title": "TCC",
                "student_id": str(self.student.academic_id),
                "course_id": str(self.student.course_id),
                "account_id": str(uuid4()),
                "role": "admin",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        record = ThesisAuditModel.objects.get(thesis_id=response.json()["id"])
        self.assertEqual(record.account_id, self.student.account_id)
        self.assertEqual(record.academic_id, self.student.academic_id)
        self.assertEqual(record.role, Role.STUDENT)

    def test_deletion_audit_failure_restores_draft(self):
        thesis = self.create_draft()
        delete = dependencies.build_delete_thesis_use_case(self.student)

        with patch.object(delete.audit, "record", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                delete.execute(thesis.id)

        self.assertEqual(self.create.repository.find_by_id(thesis.id), thesis)
        records = ThesisAuditModel.objects.filter(thesis_id=thesis.id)
        self.assertEqual(list(records.values_list("action", flat=True)), [AuditAction.CREATED])
