from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from defense.adapters.outbound.models import Audit, Defense, Evaluation, Member, Outbox
from defense.adapters.outbound.repository import Repository
from defense.application import DefenseService
from defense.domain import Actor, DefenseError, Thesis
from defense.management.commands.run_outbox_worker import publish_next


class FlowTests(TestCase):
    def setUp(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        directory = self.enterContext(TemporaryDirectory())
        public = Path(directory) / "public.pem"
        public.write_bytes(key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        self.enterContext(self.settings(JWT_PUBLIC_KEY_FILE=str(public), JWT_ISSUER="issuer", JWT_AUDIENCE="aud"))
        self.key = key
        self.course, self.advisor, self.student, self.coordinator = [uuid4() for _ in range(4)]
        self.thesis = Thesis(uuid4(), self.course, self.student, self.advisor, "advisor_approved")
        self.repo = Repository()
        self.theses = Mock()
        self.theses.get.return_value = self.thesis
        self.enterContext(patch("defense.adapters.inbound.views.build_service",
                                return_value=DefenseService(self.repo, self.theses)))
        self.client = APIClient()
        self.root = "/api/defenses/"

    def login(self, role, academic_id, **claims):
        now = datetime.now(timezone.utc)
        token = jwt.encode({
            "sub": str(uuid4()), "academic_id": str(academic_id), "course_id": str(self.course),
            "role": role, "iss": "issuer", "aud": "aud", "iat": now,
            "exp": now + timedelta(minutes=5), **claims,
        }, self.key, algorithm="RS256", headers={"typ": "at+jwt"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def create(self):
        self.login("coordinator", self.coordinator)
        response = self.client.post(self.root, {"thesis_id": self.thesis.id}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return self.root + response.data["id"] + "/"

    def add_internal(self, url, person):
        response = self.client.post(url + "members/", {"kind": "internal", "academic_id": person}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return url + "members/" + response.data["id"] + "/"

    def test_jwt_scope_and_approval(self):
        self.assertEqual(self.client.get(self.root).status_code, 401)
        self.login("advisor", self.advisor, aud="invalid")
        self.assertEqual(self.client.get(self.root).status_code, 401)
        self.login("advisor", self.advisor, exp=datetime.now(timezone.utc) - timedelta(seconds=1))
        self.assertEqual(self.client.get(self.root).status_code, 401)
        self.login("advisor", uuid4())
        self.assertEqual(self.client.post(self.root, {"thesis_id": self.thesis.id}).status_code, 404)
        self.login("advisor", self.advisor)
        self.theses.get.return_value = Thesis(self.thesis.id, self.course, self.student, self.advisor, "submitted")
        self.assertEqual(self.client.post(self.root, {"thesis_id": self.thesis.id}).status_code, 409)
        self.theses.get.return_value = self.thesis
        url = self.create()
        self.login("student", self.student)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(self.root, {"thesis_id": self.thesis.id}).status_code, 403)
        self.login("student", uuid4())
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login("admin", uuid4())
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_external_expiration_and_single_use(self):
        url = self.create()
        response = self.client.post(url + "members/", {
            "kind": "external", "name": "Visitante", "email": "guest@example.org",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response["Cache-Control"], "no-store")
        token = response.data["token"]
        member = Member.objects.get(pk=response.data["id"])
        self.assertNotEqual(token, member.token_hash)
        reply_url = f"{url}members/{member.id}/external-response/"
        self.client.credentials()
        body = {"accept": True, "token": token}
        valid_expiration = member.expires_at
        Member.objects.filter(pk=member.pk).update(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        self.assertEqual(self.client.post(reply_url, body, format="json").status_code, 403)
        Member.objects.filter(pk=member.pk).update(expires_at=valid_expiration)
        self.assertEqual(self.client.post(reply_url, body, format="json").status_code, 200)
        self.assertEqual(self.client.post(reply_url, body, format="json").status_code, 403)
        self.assertEqual(self.client.post(url + "evaluations/", body, format="json").status_code, 401)

    def test_schedule_hold_evaluations_and_result(self):
        url = self.create()
        advisor_invite = self.add_internal(url, self.advisor)
        coordinator_invite = self.add_internal(url, self.coordinator)
        start = datetime.now(timezone.utc) + timedelta(days=1)
        slot = {"starts_at": start.isoformat(), "ends_at": (start + timedelta(hours=1)).isoformat(), "venue": "Sala A"}
        self.assertEqual(self.client.post(url + "schedule/", slot, format="json").status_code, 409)
        self.assertEqual(self.client.post(advisor_invite + "response/", {"accept": True}).status_code, 403)
        self.assertEqual(self.client.post(coordinator_invite + "response/", {"accept": True}).status_code, 200)
        self.login("advisor", self.advisor)
        self.assertEqual(self.client.post(advisor_invite + "response/", {"accept": True}).status_code, 200)
        self.assertEqual(self.client.post(url + "schedule/", slot, format="json").status_code, 200)
        self.assertEqual(self.client.post(url + "hold/").status_code, 409)
        Defense.objects.update(starts_at=start - timedelta(days=2), ends_at=start - timedelta(days=1, hours=1))
        self.assertEqual(self.client.post(url + "hold/").status_code, 200)
        score = {"grade": "8.50", "opinion": "Parecer privado", "recommendation": "conditional"}
        self.assertEqual(self.client.post(url + "evaluations/", score, format="json").status_code, 201)
        self.assertEqual(self.client.post(url + "evaluations/", score, format="json").status_code, 409)
        self.assertEqual(self.client.get(url + "result/").status_code, 409)
        self.login("coordinator", self.coordinator)
        self.assertEqual(self.client.post(url + "evaluations/", {**score, "grade": 9.50}, format="json").status_code, 201)
        self.assertEqual(self.client.get(url + "result/").data, {"result": "approved_with_conditions", "average": "9.00"})
        self.assertEqual(self.client.post(url + "evaluations/", score, format="json").status_code, 409)
        self.assertEqual(Outbox.objects.count(), 4)
        self.assertTrue(Audit.objects.filter(action="completed").exists())
        self.assertFalse(any("opinion" in event.data for event in Outbox.objects.all()))

    def test_rollback_when_outbox_fails(self):
        url = self.create()
        with patch.object(self.repo, "event", side_effect=RuntimeError), self.assertRaises(RuntimeError):
            self.client.post(url + "cancel/")
        self.assertEqual(Defense.objects.get().status, "proposed")
        self.assertEqual(Audit.objects.count(), 1)
        self.assertFalse(Outbox.objects.exists())

    def test_outbox_retries_same_id(self):
        url = self.create()
        self.assertEqual(self.client.post(url + "cancel/").status_code, 200)
        event = Outbox.objects.get()
        producer = Mock()
        producer.flush.return_value = 1
        self.assertFalse(publish_next(producer))
        event.refresh_from_db()
        self.assertIsNone(event.published_at)
        self.assertEqual(event.attempts, 1)
        producer.produce.side_effect = lambda *args, **kwargs: kwargs["on_delivery"](None, None)
        producer.flush.return_value = 0
        self.assertTrue(publish_next(producer))
        event.refresh_from_db()
        self.assertIsNotNone(event.published_at)
        self.assertEqual(producer.produce.call_args_list[0].kwargs["value"],
                         producer.produce.call_args_list[1].kwargs["value"])


class ScheduleConcurrencyTests(TransactionTestCase):
    def test_only_one_concurrent_reservation(self):
        course, advisor = uuid4(), uuid4()
        actor = Actor(uuid4(), advisor, "advisor", course)
        repo = Repository()
        theses = [Thesis(uuid4(), course, uuid4(), advisor, "advisor_approved") for _ in range(2)]
        defenses = [repo.create(thesis) for thesis in theses]
        for defense in defenses:
            repo.invite(defense, {"kind": "internal", "academic_id": advisor, "invite_status": "confirmed"})
        start = datetime.now(timezone.utc) + timedelta(days=1)
        fields = {"starts_at": start, "ends_at": start + timedelta(hours=1), "venue": "Sala concorrente"}
        client = Mock()
        client.get.side_effect = lambda pk, token: next(thesis for thesis in theses if thesis.id == pk)

        def attempt(defense):
            try:
                DefenseService(Repository(), client).schedule(defense.id, actor, "jwt", fields)
                return True
            except DefenseError:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(list(pool.map(attempt, defenses)), [True, False])
        self.assertEqual(Outbox.objects.filter(event_type="defense.scheduled").count(), 1)
