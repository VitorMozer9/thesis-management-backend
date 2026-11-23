from time import time
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import override_settings


class TestTokenAuthority:

    def __init__(self, test):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_key = self.key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")

        test.enterContext(override_settings(
            THESIS_JWT_ISSUER="urn:test:identity",
            THESIS_JWT_AUDIENCE="urn:test:theses",
            THESIS_JWT_PUBLIC_KEY=public_key,
        ))
        self.client = test.client

    def login(self, academic_id, course_id, role="student", **overrides):
        now = int(time())
        claims = {
            "iss": "urn:test:identity",
            "aud": "urn:test:theses",
            "sub": str(uuid4()),
            "academic_id": str(academic_id),
            "course_id": str(course_id),
            "role": role,
            "iat": now,
            "exp": now + 300,
            **overrides,
        }
        token = jwt.encode(claims, self.key, algorithm="RS256", headers={"typ": "at+jwt"})
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"
