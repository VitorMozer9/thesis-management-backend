import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import time
from unittest.mock import Mock, patch
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from config.dependencies import service
from repository.adapters import catalog
from repository.adapters.defenses import DefenseClient
from repository.adapters.events import consume, decode
from repository.adapters.theses import ThesisClient
from repository.domain import Actor, Conflict, Forbidden
from repository.models import Audit, CatalogRevision, Entry, InvalidMessage, PublicationOutbox, Receipt


class PublicationTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = Path(self.temp.name) / "public.pem"
        public.write_bytes(self.key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        self.enterContext(override_settings(MEDIA_ROOT=self.temp.name, JWT_PUBLIC_KEY_FILE=public,
                                           JWT_AUDIENCE="test", JWT_ISSUER="test", SECRET_KEY="test-secret"))
        self.verify = self.enterContext(patch.object(ThesisClient, "verify", return_value="0" * 64))
        self.defense = self.enterContext(patch.object(DefenseClient, "verify", return_value=2026))
        self.actor = Actor(uuid4(), uuid4(), "coordinator", uuid4())
        self.thesis = uuid4()
        self.base = "/api/repository/"
        self.admin = f"{self.base}admin/{self.thesis}/"
        self.client = APIClient()
        self.app = service()
        self.metadata = {"title": "Sistemas distribuídos", "author": "Maria Silva", "advisor": "João Alves",
                         "keywords": "redes\ndados"}
        self.envelope = {
            "event_id": str(uuid4()), "event_type": "defense.completed", "aggregate_id": str(uuid4()),
            "version": 1, "occurred_at": datetime.now(timezone.utc).isoformat(),
            "data": {"thesis_id": str(self.thesis), "course_id": str(self.actor.course_id),
                     "result": "approved", "defense_year": 2026},
        }
        self.envelope["data"]["defense_id"] = self.envelope["aggregate_id"]

    def login(self, role):
        claims = {"sub": str(self.actor.account_id), "academic_id": str(self.actor.academic_id),
                  "role": role, "course_id": str(self.actor.course_id), "iat": int(time()),
                  "exp": int(time()) + 120, "aud": "test", "iss": "test"}
        token = jwt.encode(claims, self.key, algorithm="RS256", headers={"typ": "at+jwt"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def complete(self, result="approved"):
        self.envelope["data"]["result"] = result
        self.app.complete(decode(json.dumps(self.envelope).encode()))

    def edit(self):
        return self.app.administer(self.thesis, self.actor, "test", metadata=self.metadata)

    def doc(self, kind, digest=None):
        content = b"%PDF-1.7\n" + kind.encode() + b"\n%%EOF"
        data = {"kind": kind, "file": SimpleUploadedFile("arquivo.pdf", content),
                "sha256": digest or hashlib.sha256(content).hexdigest()}
        return self.app.administer(self.thesis, self.actor, "test", document=data)

    def prepare(self):
        self.edit()
        self.doc("authorization")
        self.doc("final")

    def test_documents_first_then_replayed_approval(self):
        self.prepare()
        self.assertEqual(self.client.get(f"{self.base}{self.thesis}/pdf/").status_code, 404)
        self.complete()
        self.complete()
        self.assertEqual(Receipt.objects.count(), 1)
        self.assertEqual(PublicationOutbox.objects.get().thesis_id, self.thesis)
        self.assertEqual(Audit.objects.filter(action="published").count(), 1)
        self.assertEqual(Audit.objects.get(action="published").event_id.hex, self.envelope["event_id"].replace("-", ""))
        response = self.client.get(f"{self.base}{self.thesis}/pdf/")
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.7\nfinal\n%%EOF")
        data = self.client.get(f"{self.base}{self.thesis}/").json()
        self.assertNotIn("term_hash", data)
        with self.assertRaises(Conflict):
            self.doc("corrected")

    def test_rejected_never_public(self):
        self.complete("rejected")
        self.prepare()
        self.assertIsNone(Entry.objects.get().published_at)
        self.assertEqual(self.client.get(self.base).json()["results"], [])

    def test_missing_final_pdf(self):
        self.complete()
        self.edit()
        self.doc("authorization")
        self.assertIsNone(Entry.objects.get().published_at)

    def test_missing_authorization(self):
        self.complete()
        self.edit()
        self.doc("final")
        self.assertIsNone(Entry.objects.get().published_at)
        self.assertEqual(self.doc("authorization"), "published")

    def test_conditions_require_new_corrected_file(self):
        self.prepare()
        self.complete("approved_with_conditions")
        self.assertIsNone(Entry.objects.get().published_at)
        self.verify.return_value = None
        with self.assertRaises(Conflict):
            self.doc("corrected")
        self.verify.return_value = hashlib.sha256(b"%PDF-1.7\ncorrected\n%%EOF").hexdigest()
        with self.assertRaises(Conflict):
            self.doc("corrected")
        self.verify.return_value = "0" * 64
        self.assertEqual(self.doc("corrected"), "published")

    def test_legacy_year_verified_with_defense(self):
        self.prepare()
        del self.envelope["data"]["defense_year"]
        self.metadata["reported_year"] = 2024
        self.edit()
        self.defense.return_value = 2025
        self.complete()
        self.assertIsNone(Entry.objects.get().published_at)
        self.metadata["reported_year"] = 2025
        self.assertEqual(self.edit(), "published")
        self.assertEqual(Entry.objects.get().defense_year, 2025)

    def test_integrity_and_audit_rollback(self):
        with self.assertRaises(Conflict):
            self.doc("final", "1" * 64)
        self.assertFalse(Entry.objects.exists())
        self.assertFalse(Audit.objects.exists())
        self.prepare()
        entry = Entry.objects.get()
        (Path(self.temp.name) / str(self.thesis) / entry.final_hash).write_bytes(b"corrompido")
        with self.assertRaises(OSError):
            self.complete()
        self.assertFalse(Receipt.objects.exists())
        self.assertFalse(Audit.objects.filter(action="published").exists())
        self.assertFalse(PublicationOutbox.objects.exists())

    def test_jwt_and_scope(self):
        url = self.admin + "metadata/"
        data = dict(self.metadata, keywords=["redes"])
        self.assertEqual(self.client.put(url, data, format="json").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalido")
        self.assertEqual(self.client.put(url, data, format="json").status_code, 401)
        self.login("student")
        self.assertEqual(self.client.put(url, data, format="json").status_code, 403)
        self.login("admin")
        self.assertEqual(self.client.put(url, dict(data, approved=True), format="json").status_code, 400)
        self.assertEqual(self.client.put(url, data, format="json").status_code, 200)
        self.verify.side_effect = Forbidden
        self.assertEqual(self.client.put(url, data, format="json").status_code, 403)
        self.assertEqual(Audit.objects.get().actor_id, self.actor.account_id)

    def test_offset_after_persistence_and_quarantine(self):
        message, consumer = Mock(), Mock()
        message.topic.return_value, message.partition.return_value, message.offset.return_value = "test", 0, 1
        message.value.return_value = json.dumps(self.envelope).encode()
        consumer.commit.side_effect = lambda **kwargs: self.assertTrue(Receipt.objects.exists())
        consume(message, consumer, self.app)
        consumer.commit.assert_called_once_with(message=message, asynchronous=False)
        consumer.reset_mock()
        with patch.object(self.app, "complete", side_effect=OSError), self.assertRaises(OSError):
            consume(message, consumer, self.app)
        consumer.commit.assert_not_called()
        message.value.return_value = b"{"
        consume(message, consumer, self.app)
        self.assertEqual(InvalidMessage.objects.count(), 1)

    def test_multipart_and_authorized_correction(self):
        self.login("coordinator")
        url = self.admin + "documents/"
        for kind in ("final", "corrected"):
            content = b"%PDF-1.7\n" + kind.encode() + b"\n%%EOF"
            fields = {"kind": kind, "file": SimpleUploadedFile("../../outside.pdf", content),
                      "sha256": hashlib.sha256(content).hexdigest()}
            self.assertEqual(self.client.post(url, fields, format="multipart").json(), {"state": "pending"})
        self.assertTrue(Audit.objects.filter(action="corrected_replaced", actor_id=self.actor.account_id).exists())
        self.assertEqual(Entry.objects.get().final_hash, fields["sha256"])
        self.assertEqual(len(list((Path(self.temp.name) / str(self.thesis)).iterdir())), 2)

    def test_mismatched_result_quarantined_without_publication(self):
        self.prepare()
        self.defense.side_effect = Conflict("Banca incompatível.")
        message, consumer = Mock(), Mock()
        message.topic.return_value, message.partition.return_value, message.offset.return_value = "test", 0, 2
        message.value.return_value = json.dumps(self.envelope).encode()
        self.assertEqual(consume(message, consumer, self.app), "inconsistent_completion")
        self.assertFalse(Receipt.objects.exists())
        self.assertIsNone(Entry.objects.get().published_at)
        consumer.commit.assert_called_once()

    def test_search_filters_and_cache_generation(self):
        cache, values = Mock(), {}
        cache.get.side_effect = values.get
        cache.setex.side_effect = lambda key, ttl, data: values.update({key: data})
        self.enterContext(patch.object(catalog, "redis_client", return_value=cache))
        self.prepare()
        self.complete()
        filters = {"title": "distribuídos", "author": "silva", "advisor": "João Alves", "keywords": "redes",
                   "year": 2026, "course_id": str(self.actor.course_id)}
        for key, value in filters.items():
            with self.subTest(key=key):
                self.assertEqual(len(self.client.get(self.base, {key: value}).json()["results"]), 1)
                invalid = {"year": 2023, "course_id": str(uuid4())}.get(key, "ausente")
                self.assertEqual(self.client.get(self.base, {key: invalid}).json()["results"], [])
        self.client.get(self.base, filters)
        with patch.object(catalog, "search", side_effect=AssertionError):
            self.assertEqual(len(self.client.get(self.base, filters).json()["results"]), 1)
        revision = CatalogRevision.objects.get().revision
        self.thesis = uuid4()
        self.envelope.update(event_id=str(uuid4()), aggregate_id=str(uuid4()))
        self.envelope["data"].update(thesis_id=str(self.thesis), defense_id=self.envelope["aggregate_id"])
        self.prepare()
        self.complete()
        self.assertNotEqual(CatalogRevision.objects.get().revision, revision)
        self.assertEqual(len(self.client.get(self.base, filters).json()["results"]), 2)
        self.assertTrue(self.client.get(self.base, {"page_size": 1}).json()["has_next"])
