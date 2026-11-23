from uuid import uuid4

from django.test import override_settings

from identity.adapters.outbound.persistence.models import User
from identity.domain.account import Role
from identity.tests.support import IdentityTestCase


class LoginTests(IdentityTestCase):

    def setUp(self):
        super().setUp()

        self.account = self.provision()

    def test_valid_login_returns_bearer_access_token(self):
        response = self.login(self.account.email)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response.json()["token_type"], "Bearer")
        self.assertEqual(response.json()["expires_in"], 300)
        self.assertEqual(self.decode(response.json()["access_token"])["sub"], str(self.account.id))

    def test_login_email_is_case_insensitive(self):
        self.assertEqual(self.login(self.account.email.upper()).status_code, 200)

    def test_invalid_attempts_share_generic_response(self):
        inactive = self.provision(is_active=False)

        responses = {
            "wrong_password": self.login(self.account.email, "Wrong-Password-123"),
            "unknown_email": self.login(f"{uuid4().hex}@example.edu"),
            "inactive": self.login(inactive.email),
        }

        for case, response in responses.items():
            with self.subTest(case=case):
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.json(), {"detail": "Invalid credentials."})
                self.assertNotIn("access_token", response.json())

    def test_deactivated_account_cannot_login(self):
        User.objects.filter(id=self.account.id).update(is_active=False)

        self.assertEqual(self.login(self.account.email).status_code, 401)

    def test_body_cannot_choose_privileged_claims(self):
        response = self.login(
            self.account.email,
            role="admin",
            academic_id=str(uuid4()),
            course_id=str(uuid4()),
            assignable_advisor_ids=[str(uuid4())],
        )

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access_token", response.json())

    def test_token_claims_come_from_stored_account(self):
        claims = self.decode(self.issue_token(self.account))

        self.assertEqual(claims["role"], Role.STUDENT)
        self.assertEqual(claims["academic_id"], str(self.account.academic_id))
        self.assertEqual(claims["course_id"], str(self.course_id))
        self.assertNotIn("assignable_advisor_ids", claims)

    def test_account_without_course_cannot_receive_token(self):
        admin = self.provision(role=Role.ADMIN, course_id=None)

        self.assertEqual(self.login(admin.email).status_code, 403)

    def test_malformed_requests_are_rejected(self):
        cases = (
            {},
            {"email": "not-an-email", "password": "x"},
            {"email": self.account.email},
        )

        for body in cases:
            with self.subTest(body=body):
                response = self.client.post("/api/auth/login/", body, content_type="application/json")
                self.assertEqual(response.status_code, 400)

        form = self.client.post("/api/auth/login/", {"email": self.account.email, "password": "x"})

        self.assertEqual(form.status_code, 415)

    def test_repeated_failures_are_rate_limited(self):
        with override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "100/m/ip,2/5m/key"}):
            for _ in range(2):
                self.assertEqual(self.login(self.account.email, "Wrong-Password-123").status_code, 401)

            blocked = self.login(self.account.email)

        self.assertEqual(blocked.status_code, 429)
        self.assertNotIn("access_token", blocked.json())

    def test_missing_signing_configuration_returns_503(self):
        with override_settings(IDENTITY_JWT_PRIVATE_KEY=""):
            self.assertEqual(self.login(self.account.email).status_code, 503)

    def test_invalid_signing_key_returns_503(self):
        with override_settings(IDENTITY_JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\ninvalid\n"):
            self.assertEqual(self.login(self.account.email).status_code, 503)
