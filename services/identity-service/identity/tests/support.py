from functools import lru_cache
from uuid import uuid4

import jwt

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from django.test import TestCase, override_settings

from config import dependencies
from identity.domain.account import Account, Role


TEST_ISSUER = "urn:test:identity"
TEST_AUDIENCE = "urn:test:api"
TEST_PASSWORD = "Correct-Horse-42-Battery"


@lru_cache(maxsize=4)
def generate_key(bits: int = 2048) -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=bits)


def private_pem(key: RSAPrivateKey, password: bytes | None = None) -> str:
    encryption = (
        serialization.BestAvailableEncryption(password) if password else serialization.NoEncryption()
    )

    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        encryption,
    ).decode("ascii")


def public_pem(key: RSAPrivateKey) -> str:
    return key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


class IdentityTestCase(TestCase):

    def setUp(self):
        self.key = generate_key()
        self.course_id = uuid4()

        self.enterContext(override_settings(
            IDENTITY_JWT_PRIVATE_KEY=private_pem(self.key),
            IDENTITY_JWT_ISSUER=TEST_ISSUER,
            IDENTITY_JWT_AUDIENCE=TEST_AUDIENCE,
            IDENTITY_ACCESS_TOKEN_TTL_SECONDS=300,
            CACHES={
                "default": {
                    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                    "LOCATION": f"identity-test-{uuid4().hex}",
                }
            },
        ))

    def provision(self, role: Role = Role.STUDENT, **changes) -> Account:
        fields = {
            "name": "Ana Souza",
            "email": f"{uuid4().hex[:12]}@example.edu",
            "role": role,
            "course_id": self.course_id,
            "password": TEST_PASSWORD,
        }
        fields.update(changes)

        return dependencies.build_provision_account_use_case().execute(**fields)

    def login(self, email: str, password: str = TEST_PASSWORD, **extra):
        return self.client.post(
            "/api/auth/login/",
            {"email": email, "password": password, **extra},
            content_type="application/json",
        )

    def issue_token(self, account: Account) -> str:
        response = self.login(account.email)
        self.assertEqual(response.status_code, 200, response.content)

        return response.json()["access_token"]

    def decode(self, token: str) -> dict:
        return jwt.decode(
            token,
            self.key.public_key(),
            algorithms=["RS256"],
            issuer=TEST_ISSUER,
            audience=TEST_AUDIENCE,
        )
