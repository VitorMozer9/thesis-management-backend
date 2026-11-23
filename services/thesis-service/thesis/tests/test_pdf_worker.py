import json
import os
import time
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import skipUnless
from unittest.mock import Mock, patch
from uuid import uuid4

from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, TransactionTestCase
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from config.dependencies import build_process_submitted_pdf_use_case, build_submit_thesis_use_case
from thesis.adapters.inbound.kafka_pdf_consumer import PdfConsumerError, PdfEventConsumer, parse_event
from thesis.adapters.outbound.messaging.kafka_event_publisher import KafkaEventPublisher
from thesis.adapters.outbound.persistence.models import ThesisModel
from thesis.adapters.outbound.persistence.pdf_extraction import PdfExtractionModel
from thesis.adapters.outbound.storage.pdf_text import PypdfTextExtractor
from thesis.application.identity import AcademicIdentity, Role
from thesis.application.ports.pdf_extraction import InvalidPdf, PdfFailure
from thesis.domain.entities.thesis import Thesis
from thesis.domain.events.thesis_events import ThesisSubmittedEvent


def make_pdf(text=None, password=None):
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    if text:
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        page["/Resources"][NameObject("/Font")] = DictionaryObject({NameObject("/F1"): font})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 20 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)

    if password:
        writer.encrypt(password)
    data = BytesIO()
    writer.write(data)
    return data.getvalue()


def serialized_event(event):
    producer = Mock()
    producer.flush.return_value = 0
    KafkaEventPublisher(producer, "test").publish(event)
    return producer.produce.call_args.kwargs["value"]


class PdfTextTests(SimpleTestCase):

    def test_valid_text(self):
        self.assertEqual(PypdfTextExtractor().extract(make_pdf("Academic research")), "Academic research")

    def test_permanent_failures(self):
        for pdf, reason in (
            (make_pdf(), PdfFailure.NO_TEXT),
            (make_pdf(password="test"), PdfFailure.ENCRYPTED),
            (b"%PDF-broken", PdfFailure.CORRUPT),
        ):
            with self.subTest(reason=reason), self.assertRaises(InvalidPdf) as raised:
                PypdfTextExtractor().extract(pdf)
            self.assertEqual(raised.exception.reason, reason)

    def test_page_limit(self):
        writer = PdfWriter()
        for _ in range(501):
            writer.add_blank_page(width=100, height=100)
        data = BytesIO()
        writer.write(data)

        with self.assertRaises(InvalidPdf) as raised:
            PypdfTextExtractor().extract(data.getvalue())
        self.assertEqual(raised.exception.reason, PdfFailure.PAGE_LIMIT)

    def test_invalid_envelopes(self):
        event = ThesisSubmittedEvent(thesis_id=uuid4())
        envelope = json.loads(serialized_event(event))
        for changes in (
            {"version": True}, {"version": 2}, {"data": {}}, {"aggregate_id": str(uuid4())},
            {"event_id": "bad"}, {"occurred_at": "2026-01-01"},
        ):
            with self.subTest(changes=changes), self.assertRaises(PdfConsumerError):
                parse_event(json.dumps({**envelope, **changes}).encode())


class SubmissionFixture:

    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.enterContext(self.settings(MEDIA_ROOT=self.root))
        actor = AcademicIdentity(uuid4(), Role.STUDENT, uuid4(), uuid4(), frozenset())
        submit = build_submit_thesis_use_case(actor)
        pdf = make_pdf("Texto privado")
        self.key = "test.pdf"
        (self.root / self.key).write_bytes(pdf)
        draft = (
            Thesis.create_draft("TCC", "Resumo", actor.academic_id, actor.course_id)
            .assign_advisor(uuid4())
            .change_keywords(("pesquisa",))
            .attach_file(self.key, sha256(pdf).hexdigest())
        )
        submit.repository.save(draft)
        submit.execute(draft.id)
        self.result = PdfExtractionModel.objects.get(thesis_id=draft.id)
        self.event = ThesisSubmittedEvent(thesis_id=draft.id, event_id=self.result.event_id)
        self.processor = build_process_submitted_pdf_use_case()
        self.consumer = Mock()
        self.message = self.consumer.poll.return_value
        self.message.error.return_value = None
        self.message.value.return_value = serialized_event(self.event)
        self.consumer.commit.return_value = []
        self.worker = PdfEventConsumer(self.consumer, self.processor)


class PdfProcessingTests(SubmissionFixture, TestCase):

    def test_commit_after_persistence_and_redelivery_after_restart(self):
        self.assertEqual(self.result.status, "pending")

        def check_persisted(**kwargs):
            self.result.refresh_from_db()
            self.assertEqual(self.result.status, "completed")
            self.assertEqual(self.result.text, "Texto privado")
            self.assertIsNotNone(self.result.finished_at)
            return []

        self.consumer.commit.side_effect = check_persisted
        self.worker.poll_once()
        self.consumer.commit.assert_called_once_with(message=self.message, asynchronous=False)

        restarted = build_process_submitted_pdf_use_case()
        with patch.object(restarted.extractor, "extract") as extract:
            PdfEventConsumer(self.consumer, restarted).poll_once()
            extract.assert_not_called()

        self.assertEqual(PdfExtractionModel.objects.count(), 1)

    def test_hash_mismatch_is_terminal(self):
        (self.root / self.key).write_bytes(b"changed")
        with patch.object(self.processor.extractor, "extract") as extract:
            self.worker.poll_once()
            extract.assert_not_called()

        self.result.refresh_from_db()
        self.assertEqual((self.result.status, self.result.failure_code, self.result.text),
                         ("failed", "hash_mismatch", ""))
        self.consumer.commit.assert_called_once()

    def test_other_type_ignored_and_malformed_event_stops(self):
        self.message.value.return_value = b'{"event_type":"thesis.created"}'
        self.worker.poll_once()
        self.consumer.commit.assert_called_once()

        self.consumer.commit.reset_mock()
        self.message.value.return_value = b"invalid"
        with self.assertRaises(PdfConsumerError):
            self.worker.poll_once()
        self.consumer.commit.assert_not_called()
        self.result.refresh_from_db()
        self.assertEqual(self.result.status, "pending")

    def test_commit_failure_then_redelivery_keeps_existing_result(self):
        self.consumer.commit.side_effect = [RuntimeError("broker"), []]
        with self.assertRaises(PdfConsumerError):
            self.worker.poll_once()

        self.result.refresh_from_db()
        finished_at = self.result.finished_at
        self.assertEqual(self.result.status, "completed")

        with patch.object(self.processor.extractor, "extract") as extract:
            self.worker.poll_once()
            extract.assert_not_called()

        self.result.refresh_from_db()
        self.assertEqual(self.result.finished_at, finished_at)

    def test_storage_failure_then_restart(self):
        with patch.object(self.processor.storage, "open", side_effect=OSError):
            with self.assertRaises(PdfConsumerError):
                self.worker.poll_once()

        self.consumer.commit.assert_not_called()
        self.result.refresh_from_db()
        self.assertEqual(self.result.status, "processing")
        PdfEventConsumer(self.consumer, build_process_submitted_pdf_use_case()).poll_once()
        self.result.refresh_from_db()
        self.assertEqual(self.result.status, "completed")

    def test_database_failure_without_commit(self):
        with patch.object(self.processor.repository, "finish", side_effect=OperationalError):
            with self.assertRaises(PdfConsumerError):
                self.worker.poll_once()

        self.consumer.commit.assert_not_called()
        self.result.refresh_from_db()
        self.assertIsNone(self.result.finished_at)

    def test_changed_file_discards_old_text_and_deletion_cascades(self):
        def replace_file(content):
            ThesisModel.objects.filter(pk=self.event.thesis_id).update(file_key="replacement.pdf")
            return "Texto do arquivo anterior"

        with patch.object(self.processor.extractor, "extract", side_effect=replace_file):
            self.worker.poll_once()

        self.result.refresh_from_db()
        self.assertEqual((self.result.failure_code, self.result.text), ("stale_file", ""))
        ThesisModel.objects.filter(pk=self.event.thesis_id).delete()
        self.assertFalse(PdfExtractionModel.objects.exists())


@skipUnless(os.getenv("TEST_KAFKA_BOOTSTRAP_SERVERS"), "Requer broker Kafka de teste.")
class KafkaPdfIntegrationTests(SubmissionFixture, TransactionTestCase):

    def test_real_broker_commits_processed_submission(self):
        brokers = os.environ["TEST_KAFKA_BOOTSTRAP_SERVERS"]
        topic = f"test.thesis.pdf.{uuid4().hex}"
        admin = AdminClient({"bootstrap.servers": brokers})
        creation = admin.create_topics([NewTopic(topic, 1, 1)], request_timeout=10)
        creation[topic].result(timeout=15)
        self.addCleanup(lambda: admin.delete_topics([topic], request_timeout=10)[topic].result(timeout=15))

        producer = Producer({"bootstrap.servers": brokers, "message.timeout.ms": 10000})
        KafkaEventPublisher(producer, topic).publish(self.event)
        client = Consumer({
            "bootstrap.servers": brokers,
            "group.id": topic,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
        })
        self.addCleanup(client.close)
        client.subscribe([topic])
        worker = PdfEventConsumer(client, self.processor)
        deadline = time.monotonic() + 25

        while self.result.status != "completed" and time.monotonic() < deadline:
            worker.poll_once()
            self.result.refresh_from_db()

        self.assertEqual(self.result.text, "Texto privado")
        committed = client.committed([TopicPartition(topic, 0)], timeout=10)
        self.assertEqual(committed[0].offset, 1)
