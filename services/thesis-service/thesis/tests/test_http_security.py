from dataclasses import replace
from time import time
from uuid import uuid4

import jwt
from django.core.files.uploadedfile import SimpleUploadedFile
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase

from thesis.adapters.outbound.persistence.django_thesis_repository import DjangoThesisRepository
from thesis.adapters.outbound.persistence.outbox_models import OutboxEventModel
from thesis.domain.entities.thesis import Thesis
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import ThesisNotEditableError
from thesis.tests.token_authority import TestTokenAuthority


class ThesisSecurityTests(TestCase):

    def setUp(self):
        self.authority = TestTokenAuthority(self)
        self.student = uuid4()
        self.advisor = uuid4()
        self.course = uuid4()
        self.repository = DjangoThesisRepository()
        self.collection = "/api/theses/"

        self.draft = (
            Thesis.create_draft("Security", "Abstract", self.student, self.course)
            .assign_advisor(self.advisor)
            .change_keywords(("security",))
            .attach_file("document.pdf", "a" * 64)
        )
        self.repository.save(self.draft)
        self.detail = f"{self.collection}{self.draft.id}/"

    def test_missing_and_malformed_credentials(self):
        for credential in ("", "Bearer malformed", "Basic credentials"):
            with self.subTest(credential=credential):
                response = self.client.get(self.detail, HTTP_AUTHORIZATION=credential)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response["WWW-Authenticate"], "Bearer")

    def test_invalid_signed_claims(self):
        for overrides in (
            {"exp": int(time()) - 1},
            {"iat": int(time()) + 3600},
            {"aud": "another-service"},
            {"iss": "another-issuer"},
            {"role": "superuser"},
            {"sub": None},
            {"academic_id": "invalid"},
            {"course_id": None},
            {"assignable_advisor_ids": "invalid"},
        ):
            with self.subTest(overrides=overrides):
                claims = {"academic_id": self.student, "course_id": self.course, **overrides}
                self.authority.login(**claims)

                self.assertEqual(self.client.get(self.detail).status_code, 401)

    def test_untrusted_key_and_missing_trust(self):
        self.authority.login(self.student, self.course)
        with self.settings(THESIS_JWT_PUBLIC_KEY=""):
            self.assertEqual(self.client.get(self.detail).status_code, 401)

        self.authority.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.authority.login(self.student, self.course)
        self.assertEqual(self.client.get(self.detail).status_code, 401)

    def test_foreign_student_cannot_read_or_mutate(self):
        self.authority.login(uuid4(), self.course)
        responses = [
            self.client.post(
                self.detail + "pdf/",
                {"file": SimpleUploadedFile("test.pdf", b"%PDF-test")},
            ),
            self.client.get(self.detail),
            self.client.get(self.detail + "upload-status/"),
            self.client.patch(self.detail, {"title": "Changed"}, content_type="application/json"),
            self.client.post(self.detail + "submit/"),
            self.client.delete(self.detail),
        ]
        self.assertEqual([response.status_code for response in responses], [404] * len(responses))
        self.assertEqual(self.repository.find_by_id(self.draft.id), self.draft)
        self.assertFalse(OutboxEventModel.objects.exists())

    def test_creation_is_bound_to_student_and_course(self):
        self.authority.login(self.student, self.course)

        for student, course in ((uuid4(), self.course), (self.student, uuid4())):
            payload = {"student_id": str(student), "course_id": str(course), "title": "Denied"}
            response = self.client.post(self.collection, payload, content_type="application/json")
            self.assertEqual(response.status_code, 403)

        self.assertFalse(OutboxEventModel.objects.exists())

    def test_list_scope_precedes_pagination_and_filters(self):
        foreign = replace(self.draft, id=uuid4(), student_id=uuid4(), advisor_id=uuid4())
        other_course = replace(self.draft, id=uuid4(), course_id=uuid4())
        self.repository.save(foreign)
        self.repository.save(other_course)

        for role, academic_id, expected in (
            ("student", self.student, [self.draft.id]),
            ("advisor", self.advisor, [self.draft.id]),
            ("coordinator", uuid4(), [foreign.id, self.draft.id]),
            ("admin", uuid4(), [foreign.id, self.draft.id]),
        ):
            with self.subTest(role=role):
                self.authority.login(academic_id, self.course, role)
                response = self.client.get(self.collection, {"page_size": 1}).json()
                self.assertEqual([row["id"] for row in response["results"]], [str(expected[0])])
                self.assertEqual(response["has_next"], len(expected) > 1)

                filtered = self.client.get(self.collection, {"course_id": str(other_course.course_id)})
                self.assertEqual(filtered.json(), {"results": [], "has_next": False})

    def test_only_authorized_coordinator_can_assign(self):
        new_advisor = uuid4()
        assignment = {"advisor_id": str(new_advisor)}

        for role, course, grants, expected in (
            ("student", self.course, [str(new_advisor)], 403),
            ("advisor", self.course, [str(new_advisor)], 403),
            ("admin", self.course, [str(new_advisor)], 403),
            ("coordinator", self.course, [], 403),
            ("coordinator", uuid4(), [str(new_advisor)], 404),
            ("coordinator", self.course, [str(new_advisor)], 200),
        ):
            with self.subTest(role=role, expected=expected):
                self.authority.login(uuid4(), course, role, assignable_advisor_ids=grants)
                response = self.client.patch(self.detail, assignment, content_type="application/json")
                self.assertEqual(response.status_code, expected)

        self.assertEqual(self.repository.find_by_id(self.draft.id).advisor_id, new_advisor)
        mixed = {**assignment, "title": "Denied"}
        self.assertEqual(self.client.patch(self.detail, mixed, content_type="application/json").status_code, 403)

    def test_submission_and_advisor_decisions(self):
        for action, event_type in (
            ("approve", "thesis.advisor_approved"),
            ("reject", "thesis.advisor_rejected"),
        ):
            with self.subTest(action=action):
                draft = self.repository.save(replace(self.draft, id=uuid4()))
                url = f"{self.collection}{draft.id}/"
                review = f"{url}{action}/"

                self.authority.login(self.student, self.course)
                self.assertEqual(self.client.post(url + "submit/").status_code, 200)
                self.assertEqual(self.client.post(review).status_code, 403)
                self.assertEqual(self.client.delete(url).status_code, 409)

                self.authority.login(uuid4(), self.course, "advisor")
                self.assertEqual(self.client.post(review).status_code, 404)
                self.authority.login(self.advisor, self.course, "advisor")
                spoof = {"authenticated_advisor_id": str(uuid4())}
                self.assertEqual(self.client.post(review, spoof, content_type="application/json").status_code, 400)
                self.assertEqual(self.client.post(review).status_code, 200)
                self.assertEqual(self.client.post(review).status_code, 409)

                events = OutboxEventModel.objects.filter(aggregate_id=draft.id)
                self.assertCountEqual(events.values_list("event_type", flat=True), ["thesis.submitted", event_type])

    def test_delete_owner_only_and_draft_only(self):
        self.authority.login(self.student, self.course, "admin")
        self.assertEqual(self.client.delete(self.detail).status_code, 403)

        self.authority.login(self.student, self.course)
        self.assertEqual(self.client.delete(self.detail).status_code, 204)

        published = self.repository.save(replace(self.draft, id=uuid4(), status=ThesisStatus.PUBLISHED))
        self.assertEqual(self.client.delete(f"{self.collection}{published.id}/").status_code, 409)

    def test_unsigned_token_and_missing_academic_claim(self):
        self.authority.login(self.student, self.course)
        signed_token = self.client.defaults["HTTP_AUTHORIZATION"].split()[1]
        claims = jwt.decode(signed_token, options={"verify_signature": False})
        unsigned_token = jwt.encode(claims, key=None, algorithm="none", headers={"typ": "at+jwt"})
        del claims["academic_id"]
        incomplete_token = jwt.encode(
            claims, self.authority.key, algorithm="RS256", headers={"typ": "at+jwt"}
        )

        for token in (unsigned_token, incomplete_token):
            response = self.client.get(self.detail, HTTP_AUTHORIZATION=f"Bearer {token}")
            self.assertEqual(response.status_code, 401)

    def test_stale_student_update_cannot_restore_previous_advisor(self):
        replacement = uuid4()
        self.authority.login(uuid4(), self.course, "coordinator", assignable_advisor_ids=[str(replacement)])
        response = self.client.patch(
            self.detail, {"advisor_id": str(replacement)}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        with self.assertRaises(ThesisNotEditableError):
            self.repository.update_draft(self.draft.change_title("Late edit"), previous=self.draft)

        self.assertEqual(self.repository.find_by_id(self.draft.id).advisor_id, replacement)
