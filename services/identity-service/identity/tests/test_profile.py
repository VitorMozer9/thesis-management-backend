from identity.adapters.outbound.persistence.models import User
from identity.tests.support import IdentityTestCase


class ProfileTests(IdentityTestCase):

    def setUp(self):
        super().setUp()

        self.account = self.provision()

    def get_profile(self, authorization=None):
        headers = {"HTTP_AUTHORIZATION": authorization} if authorization else {}

        return self.client.get("/api/auth/me/", **headers)

    def test_requires_authentication(self):
        response = self.get_profile()

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")

    def test_returns_own_profile_without_secrets(self):
        response = self.get_profile(f"Bearer {self.issue_token(self.account)}")
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["id"], str(self.account.id))
        self.assertEqual(body["academic_id"], str(self.account.academic_id))
        self.assertEqual(body["email"], self.account.email)
        self.assertEqual(body["role"], "student")
        self.assertNotIn("password", body)

    def test_profile_belongs_to_token_subject_only(self):
        other = self.provision()

        body = self.get_profile(f"Bearer {self.issue_token(other)}").json()

        self.assertEqual(body["id"], str(other.id))

    def test_rejects_malformed_credentials(self):
        token = self.issue_token(self.account)

        for authorization in ("Bearer", f"Basic {token}", f"Bearer {token} extra", "Bearer invalid.token.value"):
            with self.subTest(authorization=authorization):
                self.assertEqual(self.get_profile(authorization).status_code, 401)

    def test_deactivated_account_loses_profile_access(self):
        token = self.issue_token(self.account)
        User.objects.filter(id=self.account.id).update(is_active=False)

        self.assertEqual(self.get_profile(f"Bearer {token}").status_code, 401)
