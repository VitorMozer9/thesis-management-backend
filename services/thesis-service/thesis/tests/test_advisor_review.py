import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from threading import Barrier
from unittest.mock import Mock, patch
from uuid import uuid4

from django.db import connections
from django.test import TestCase, TransactionTestCase

from config.dependencies import build_review_thesis_use_case
from thesis.adapters.outbound.messaging.kafka_event_publisher import KafkaEventPublisher
from thesis.adapters.outbound.persistence.django_outbox_dispatch import DjangoOutboxDispatchRepository
from thesis.adapters.outbound.persistence.outbox_models import OutboxEventModel
from thesis.application.identity import AcademicIdentity, Role
from thesis.application.exceptions import ThesisAdvisorPermissionError, ThesisNotFoundError
from thesis.application.ports.thesis_lock import ThesisAlreadyLockedError
from thesis.application.use_case.publish_outbox_events import PublishOutboxEventsUseCase
from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import InvalidThesisStatusTransitionError


def review_for(thesis):
    actor = AcademicIdentity(uuid4(), Role.ADVISOR, thesis.advisor_id, thesis.course_id, frozenset())
    return build_review_thesis_use_case(actor)


def submitted_thesis():
    return (
        Thesis.create_draft("Review", "Abstract", uuid4(), uuid4())
        .assign_advisor(uuid4())
        .change_keywords(("review",))
        .attach_file("review.pdf", "a" * 64)
        .submit()
    )


class AdvisorReviewTests(TestCase):
    def setUp(self):
        self.thesis = submitted_thesis()
        self.review = review_for(self.thesis)
        self.review.repository.save(self.thesis)

    def decide(self, decision):
        return self.review.execute(
            self.thesis.id, authenticated_advisor_id=self.thesis.advisor_id, decision=decision
        )

    def test_review_decisions_reach_publisher_and_preserve_event_id_on_retry(self):
        for decision in (ThesisStatus.ADVISOR_APPROVED, ThesisStatus.ADVISOR_REJECTED):
            with self.subTest(decision=decision):
                self.thesis = self.review.repository.save(replace(self.thesis, id=uuid4()))
                self.assertEqual(self.decide(decision).status, decision)
                stored = self.review.repository.find_by_id(self.thesis.id)
                self.assertEqual(stored.status, decision)
                event = OutboxEventModel.objects.get(aggregate_id=stored.id)
                self.assertEqual(event.event_type, f"thesis.{decision.value}")
                self.assertEqual(event.payload, {"thesis_id": str(stored.id), "version": 1})

                producer = Mock()
                producer.flush.side_effect = [1, 0]
                dispatch = PublishOutboxEventsUseCase(
                    DjangoOutboxDispatchRepository(), KafkaEventPublisher(producer, "events")
                )
                self.assertEqual(dispatch.execute().failed, 1)
                event.refresh_from_db()
                self.assertIsNone(event.published_at)
                self.assertEqual(dispatch.execute().published, 1)
                event.refresh_from_db()
                self.assertIsNotNone(event.published_at)
                self.assertEqual(event.attempts, 2)
                for call in producer.produce.call_args_list:
                    message = json.loads(call.kwargs["value"])
                    self.assertEqual(message["event_id"], str(event.id))
                    self.assertEqual(message["event_type"], event.event_type)
                    self.assertEqual(message["aggregate_id"], str(stored.id))

    def test_only_submitted_can_be_reviewed(self):
        for status in ThesisStatus:
            if status == ThesisStatus.SUBMITTED:
                continue
            self.review.repository.save(replace(self.thesis, status=status))
            for decision in (ThesisStatus.ADVISOR_APPROVED, ThesisStatus.ADVISOR_REJECTED):
                with self.subTest(status=status, decision=decision):
                    with self.assertRaises(InvalidThesisStatusTransitionError):
                        self.decide(decision)
                    self.assertEqual(self.review.repository.find_by_id(self.thesis.id).status, status)
        self.assertFalse(OutboxEventModel.objects.exists())

    def test_invalid_decision(self):
        with self.assertRaises(InvalidThesisStatusTransitionError):
            self.decide(ThesisStatus.PUBLISHED)
        self.assert_no_decision()

    def test_other_advisor_cannot_decide(self):
        for decision in (ThesisStatus.ADVISOR_APPROVED, ThesisStatus.ADVISOR_REJECTED):
            with self.assertRaises(ThesisAdvisorPermissionError):
                self.review.execute(self.thesis.id, authenticated_advisor_id=uuid4(), decision=decision)
        self.assert_no_decision()

    def test_missing_thesis(self):
        with self.assertRaises(ThesisNotFoundError):
            self.review.execute(uuid4(), authenticated_advisor_id=self.thesis.advisor_id, decision=ThesisStatus.ADVISOR_APPROVED)
        self.assert_no_decision()

    def test_contended_redis_lock(self):
        with self.review.thesis_lock.lock(self.thesis.id):
            with self.assertRaises(ThesisAlreadyLockedError):
                self.decide(ThesisStatus.ADVISOR_REJECTED)
        self.assert_no_decision()

    def test_outbox_failure_rolls_back_status(self):
        with patch.object(self.review.outbox_repository, "add", side_effect=RuntimeError("Outbox failure")):
            with self.assertRaisesRegex(RuntimeError, "Outbox failure"):
                self.decide(ThesisStatus.ADVISOR_APPROVED)
        self.assert_no_decision()

    def assert_no_decision(self):
        self.assertEqual(self.review.repository.find_by_id(self.thesis.id).status, ThesisStatus.SUBMITTED)
        self.assertFalse(OutboxEventModel.objects.exists())


class ConcurrentReviewTests(TransactionTestCase):
    def test_database_serializes_decisions_when_redis_lease_overlaps(self):
        thesis = submitted_thesis()
        review = review_for(thesis)
        review.repository.save(thesis)
        start = Barrier(2)

        def decide(decision):
            worker = review_for(thesis)
            # Simulate two holders after the first Redis lease expires.
            worker.thesis_lock = Mock()
            worker.thesis_lock.lock.return_value = nullcontext()
            try:
                start.wait(timeout=10)
                result = worker.execute(thesis.id, authenticated_advisor_id=thesis.advisor_id, decision=decision)
                return result.status
            except InvalidThesisStatusTransitionError:
                return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(decide, (ThesisStatus.ADVISOR_APPROVED, ThesisStatus.ADVISOR_REJECTED)))

        winner = review.repository.find_by_id(thesis.id).status
        self.assertCountEqual(results, [winner, None])
        self.assertEqual(OutboxEventModel.objects.get(aggregate_id=thesis.id).event_type, f"thesis.{winner.value}")
