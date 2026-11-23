from dataclasses import replace
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from config.dependencies import (
    build_delete_thesis_use_case,
    build_list_theses_use_case,
    build_update_thesis_use_case,
)
from thesis.adapters.inbound.rest.serializers import ListThesesQuerySerializer
from thesis.adapters.outbound.persistence.django_outbox_repository import (
    DjangoOutboxRepository,
)
from thesis.adapters.outbound.persistence.outbox_models import OutboxEventModel
from thesis.adapters.outbound.storage.local_file_storage import LocalFileStorage
from thesis.application.exceptions import ThesisNotFoundError
from thesis.application.ports.thesis_lock import ThesisAlreadyLockedError
from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.events.thesis_events import ThesisCreatedEvent
from thesis.domain.exceptions import (
    InvalidThesisError,
    InvalidThesisStatusTransitionError,
    ThesisNotEditableError,
)


class ThesisListTests(TestCase):

    def setUp(self):
        self.use_case = build_list_theses_use_case()
        repository = self.use_case.repository
        draft = Thesis.create_draft("Distributed storage", "", uuid4(), uuid4())

        self.first = repository.save(
            draft.assign_advisor(uuid4()).change_keywords(("Replication",))
        )
        self.second = repository.save(
            replace(draft, id=uuid4(), title="Database design", status=ThesisStatus.SUBMITTED)
        )
        self.third = repository.save(
            Thesis.create_draft("Distributed databases", "", uuid4(), uuid4())
            .change_keywords(("Backup 100%",))
        )

    def test_unfiltered_listing_and_pagination(self):
        self.assertEqual(
            self.use_case.execute(),
            ([self.third, self.second, self.first], False),
        )
        self.assertEqual(self.use_case.execute(page_size=2), ([self.third, self.second], True))
        self.assertEqual(self.use_case.execute(page_size=2, page=2), ([self.first], False))
        self.assertEqual(self.use_case.execute(page_size=2, page=3), ([], False))

    def test_individual_and_combined_filters(self):
        cases = (
            ({"student_id": self.first.student_id}, [self.second, self.first]),
            ({"advisor_id": self.first.advisor_id}, [self.first]),
            ({"course_id": self.first.course_id}, [self.second, self.first]),
            ({"status": ThesisStatus.SUBMITTED}, [self.second]),
            (
                {
                    "student_id": self.first.student_id,
                    "advisor_id": self.first.advisor_id,
                    "course_id": self.first.course_id,
                    "status": ThesisStatus.DRAFT,
                    "search": "pliCATION",
                },
                [self.first],
            ),
            ({"advisor_id": self.first.advisor_id, "status": ThesisStatus.SUBMITTED}, []),
        )

        for filters, expected in cases:
            with self.subTest(filters=filters):
                self.assertEqual(self.use_case.execute(**filters), (expected, False))

    def test_search_title_and_keywords_as_literal_substrings(self):
        for search, expected in (
            ("  DiSTRIBUTED  ", [self.third, self.first]),
            ("plica", [self.first]),
            ("100%", [self.third]),
            ("_", []),
        ):
            with self.subTest(search=search):
                self.assertEqual(self.use_case.execute(search=search), (expected, False))

    def test_query_parameter_validation(self):
        for field, value in (
            ("student_id", "bad-id"),
            ("advisor_id", "bad-id"),
            ("course_id", "bad-id"),
            ("status", "unknown"),
            ("page", 0),
            ("page", "unexpected"),
            ("page_size", 101),
            ("search", " "),
            ("search", "a" * 256),
        ):
            with self.subTest(field=field, value=value):
                serializer = ListThesesQuerySerializer(data={field: value})
                self.assertFalse(serializer.is_valid())
                self.assertIn(field, serializer.errors)

        serializer = ListThesesQuerySerializer(
            data={"student_id": str(self.first.student_id), "status": "submitted"}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(self.use_case.execute(**serializer.validated_data), ([self.second], False))

    def test_internal_pagination_and_search_bounds(self):
        for params in ({"page": 0}, {"page": 10001}, {"page_size": 101}, {"search": " "}):
            with self.subTest(params=params), self.assertRaises(InvalidThesisError):
                self.use_case.execute(**params)


class ThesisMutationTests(TestCase):

    def setUp(self):
        self.delete = build_delete_thesis_use_case()
        self.repository = self.delete.repository
        self.update = build_update_thesis_use_case()
        self.thesis = self.repository.save(
            Thesis.create_draft("Draft", "", uuid4(), uuid4())
            .attach_file("theses/draft.pdf", "a" * 64)
        )

    def test_assign_advisor_to_draft(self):
        advisor_id = uuid4()

        self.update.execute(self.thesis.id, advisor_id=advisor_id)

        self.assertEqual(self.repository.find_by_id(self.thesis.id).advisor_id, advisor_id)

    def test_non_drafts_cannot_be_deleted_or_assigned_an_advisor(self):
        for status in ThesisStatus:
            if status == ThesisStatus.DRAFT:
                continue

            with self.subTest(status=status):
                self.repository.save(replace(self.thesis, status=status))

                with self.assertRaises(InvalidThesisStatusTransitionError):
                    self.delete.execute(self.thesis.id)
                with self.assertRaises(ThesisNotEditableError):
                    self.update.execute(self.thesis.id, advisor_id=uuid4())

                stored = self.repository.find_by_id(self.thesis.id)
                self.assertEqual(stored.status, status)
                self.assertIsNone(stored.advisor_id)

    def test_delete_draft_preserves_outbox_and_rejects_stale_write(self):
        event = ThesisCreatedEvent(thesis_id=self.thesis.id)
        DjangoOutboxRepository().add(event)

        self.delete.execute(self.thesis.id)

        self.assertIsNone(self.repository.find_by_id(self.thesis.id))
        self.assertTrue(OutboxEventModel.objects.filter(pk=event.event_id).exists())

        with self.assertRaises(ThesisNotFoundError):
            self.repository.update_draft(self.thesis.change_title("Stale update"))
        with self.assertRaises(ThesisNotFoundError):
            self.delete.execute(self.thesis.id)
        with self.assertRaises(ThesisNotFoundError):
            self.update.execute(self.thesis.id, advisor_id=uuid4())

    def test_delete_draft_retains_pdf(self):
        pdf = b"%PDF-example"

        with TemporaryDirectory() as directory:
            storage = LocalFileStorage(Path(directory))
            storage.save(self.thesis.file_key, BytesIO(pdf))

            self.delete.execute(self.thesis.id)

            stored_file = Path(directory) / self.thesis.file_key
            self.assertEqual(stored_file.read_bytes(), pdf)

    def test_stale_draft_write_cannot_overwrite_a_submission(self):
        submitted = self.repository.save(
            replace(self.thesis, status=ThesisStatus.SUBMITTED)
        )

        with self.assertRaises(ThesisNotEditableError):
            self.repository.update_draft(self.thesis.change_title("Stale update"))

        self.assertEqual(self.repository.find_by_id(self.thesis.id), submitted)

    def test_delete_rollback(self):
        delete_record = self.repository.delete

        def fail_after_delete(thesis_id):
            delete_record(thesis_id)
            raise RuntimeError("Simulated transaction failure")

        with patch.object(self.repository, "delete", side_effect=fail_after_delete):
            with self.assertRaisesRegex(RuntimeError, "Simulated transaction failure"):
                self.delete.execute(self.thesis.id)

        self.assertEqual(self.repository.find_by_id(self.thesis.id), self.thesis)

    def test_delete_cannot_run_while_redis_lock_is_held(self):
        with self.delete.thesis_lock.lock(self.thesis.id):
            with self.assertRaises(ThesisAlreadyLockedError):
                self.delete.execute(self.thesis.id)

        self.assertEqual(self.repository.find_by_id(self.thesis.id), self.thesis)

    def test_http_privileged_operations_are_blocked(self):
        detail = f"/api/theses/{self.thesis.id}/"
        data = {"advisor_id": str(uuid4()), "title": "Changed"}

        for logged_in in (False, True):
            with self.subTest(logged_in=logged_in):
                if logged_in:
                    user = get_user_model().objects.create_user(username="unmapped")
                    self.client.force_login(user)

                self.assertEqual(self.client.get("/api/theses/").status_code, 405)
                self.assertEqual(self.client.delete(detail).status_code, 405)
                response = self.client.patch(detail, data, content_type="application/json")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.repository.find_by_id(self.thesis.id), self.thesis)

    def test_http_rejects_malformed_advisor_uuid(self):
        response = self.client.patch(
            f"/api/theses/{self.thesis.id}/",
            {"advisor_id": "bad-id"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("advisor_id", response.json())
