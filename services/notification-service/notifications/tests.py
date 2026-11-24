import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from config.dependencies import processor
from notifications.adapters.events import consume
from notifications.domain import Failure, MESSAGES
from notifications.models import IncomingEvent, InvalidMessage, Notification


class FlowTests(TestCase):
    def message(self, kind):
        message = Mock()
        source = kind.split(".")[0]
        event, aggregate = str(uuid4()), str(uuid4())
        data_key = "defense_id" if source == "defense" else "thesis_id"
        message.topic.return_value = source + ".events.v1"
        message.partition.return_value = 0
        message.offset.return_value = 7
        message.value.return_value = json.dumps({
            "event_id": event, "aggregate_id": aggregate, "event_type": kind, "version": 1,
            "occurred_at": datetime.now(timezone.utc).isoformat(), "data": {data_key: aggregate},
        }).encode()
        return message

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_all_events_persist_before_commit_and_send_after_restart(self):
        academic = uuid4()
        for kind in MESSAGES:
            with self.subTest(kind=kind):
                message = self.message(kind)
                consumer = Mock()
                consumer.commit.side_effect = lambda **kwargs: (
                    self.assertTrue(IncomingEvent.objects.filter(pk=json.loads(message.value())["event_id"]).exists())
                )
                consume(consumer, message)
                consume(consumer, message)
                worker = processor()
                external = {"guest@example.org"} if kind.startswith("defense.") else set()
                worker.contacts = Mock()
                worker.contacts.recipients.return_value = ({academic}, external)
                self.assertTrue(worker.run_next("events"))
                self.assertFalse(worker.run_next("events"))
                restarted = processor()
                restarted.contacts = Mock()
                restarted.contacts.account.return_value = (uuid4(), "academic@example.org")
                self.assertTrue(restarted.run_next("notifications"))
                if external:
                    self.assertTrue(restarted.run_next("notifications"))
                self.assertFalse(restarted.run_next("notifications"))
                self.assertEqual({item.to[0] for item in mail.outbox}, {"academic@example.org"} | external)
                self.assertTrue(all(item.message()["Message-ID"] for item in mail.outbox))
                mail.outbox.clear()
        self.assertEqual(IncomingEvent.objects.count(), 4)
        self.assertEqual(Notification.objects.filter(status="sent").count(), 6)

    def test_smtp_failure_retry_and_missing_address(self):
        event = IncomingEvent.objects.create(id=uuid4(), kind="thesis.submitted", aggregate_id=uuid4(), status="sent")
        delivery = Notification.objects.create(event=event, recipient=str(uuid4()), academic_id=uuid4(), subject="Teste")
        worker = processor()
        worker.contacts = Mock()
        worker.mail = Mock()
        worker.contacts.account.side_effect = Failure("source_not_found")
        worker.run_next("notifications")
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.attempts, delivery.error_code), ("pending", 1, "source_not_found"))
        worker.mail.send.assert_not_called()
        worker.contacts.account.side_effect = None
        worker.contacts.account.return_value = (uuid4(), "academic@example.org")
        worker.mail.send.side_effect = Failure("smtp_unavailable")
        worker.clock = lambda: datetime.now(timezone.utc) + timedelta(minutes=1)
        worker.run_next("notifications")
        delivery.refresh_from_db()
        self.assertIsNone(delivery.sent_at)
        self.assertEqual(delivery.error_code, "smtp_unavailable")
        worker.mail.send.side_effect = None
        worker.clock = lambda: datetime.now(timezone.utc) + timedelta(minutes=2)
        worker.run_next("notifications")
        delivery.refresh_from_db()
        self.assertEqual((delivery.status, delivery.attempts), ("sent", 3))

    def test_quarantine_and_no_commit_on_database_error(self):
        message, consumer = self.message("thesis.submitted"), Mock()
        with patch.object(IncomingEvent.objects, "get_or_create", side_effect=RuntimeError), self.assertRaises(RuntimeError):
            consume(consumer, message)
        consumer.commit.assert_not_called()
        message.value.return_value = b"invalid"
        consumer.commit.return_value = []
        consume(consumer, message)
        self.assertEqual(InvalidMessage.objects.get().reason, "invalid_envelope")
        consumer.commit.assert_called_once()

    def test_reads_only_owned_notifications(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        directory = self.enterContext(TemporaryDirectory())
        public = Path(directory) / "key.pem"
        public.write_bytes(key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        event = IncomingEvent.objects.create(id=uuid4(), kind="thesis.submitted", aggregate_id=uuid4())
        own = Notification.objects.create(event=event, recipient="own", academic_id=uuid4(), account_id=uuid4())
        other = Notification.objects.create(event=event, recipient="other", academic_id=uuid4(), account_id=uuid4())
        client = APIClient()
        root = "/api/notifications/"
        self.assertEqual(client.get(root).status_code, 401)
        client.credentials(HTTP_AUTHORIZATION="Bearer corrupted")
        self.assertEqual(client.get(root).status_code, 401)
        now = datetime.now(timezone.utc)
        token = jwt.encode({
            "sub": str(own.account_id), "academic_id": str(own.academic_id), "role": "advisor",
            "course_id": str(uuid4()), "iat": now, "exp": now + timedelta(minutes=1), "iss": "issuer", "aud": "aud",
        }, key, algorithm="RS256", headers={"typ": "at+jwt"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        with self.settings(JWT_PUBLIC_KEY_FILE=public, JWT_ISSUER="issuer", JWT_AUDIENCE="aud"):
            self.assertEqual(client.get(root).json()["results"][0]["id"], str(own.id))
            self.assertEqual(client.get(f"{root}{own.id}/").status_code, 200)
            self.assertEqual(client.get(f"{root}{other.id}/").status_code, 404)
