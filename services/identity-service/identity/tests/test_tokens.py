from io import StringIO
from time import time
from uuid import uuid4

import jwt

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from config import dependencies
from identity.adapters.outbound.security.jwt_tokens import RsaJwtVerifier
from identity.adapters.outbound.security.rsa_keys import load_private_key
from identity.application.exceptions import InvalidAccessTokenError
from identity.domain.account import Role
from identity.tests.support import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    IdentityTestCase,
    generate_key,
    private_pem,
)


REQUIRED_CLAIMS = {"iss", "aud", "sub", "academic_id", "role", "course_id", "iat", "exp"}


class AccessTokenTests(IdentityTestCase):

    def verifier(self, key=None):
        return RsaJwtVerifier((key or self.key).public_key(), TEST_ISSUER, TEST_AUDIENCE)

    def test_header_uses_fixed_rs256_access_token_type(self):
        header = jwt.get_unverified_header(self.issue_token(self.provision()))

        self.assertEqual(header["alg"], "RS256")
        self.assertEqual(header["typ"], "at+jwt")

    def test_contains_required_contract_claims(self):
        account = self.provision(role=Role.ADVISOR)
        claims = self.decode(self.issue_token(account))

        self.assertTrue(REQUIRED_CLAIMS <= claims.keys())
        self.assertEqual(claims["iss"], TEST_ISSUER)
        self.assertEqual(claims["aud"], TEST_AUDIENCE)
        self.assertIsInstance(claims["aud"], str)
        self.assertIs(type(claims["iat"]), int)
        self.assertIs(type(claims["exp"]), int)
        self.assertEqual(claims["role"], "advisor")

    def test_sub_and_academic_id_are_distinct_identifiers(self):
        account = self.provision()
        claims = self.decode(self.issue_token(account))

        self.assertEqual(claims["sub"], str(account.id))
        self.assertEqual(claims["academic_id"], str(account.academic_id))
        self.assertNotEqual(claims["sub"], claims["academic_id"])

    def test_each_role_is_signed_as_stored(self):
        for role in Role:
            with self.subTest(role=role):
                self.assertEqual(self.decode(self.issue_token(self.provision(role=role)))["role"], role.value)

    def test_expiration_uses_configured_short_lifetime(self):
        with override_settings(IDENTITY_ACCESS_TOKEN_TTL_SECONDS=120):
            claims = self.decode(self.issue_token(self.provision()))

        self.assertEqual(claims["exp"] - claims["iat"], 120)
        self.assertLessEqual(abs(claims["iat"] - int(time())), 5)

    def test_expired_token_is_rejected(self):
        account = self.provision()
        use_case = dependencies.build_issue_access_token_use_case(None)
        use_case.clock = lambda: time() - 301
        token = use_case.signer.sign(use_case.claims_for(account))

        with self.assertRaises(InvalidAccessTokenError):
            self.verifier().verify(token)

        response = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, 401)

    def test_coordinator_receives_only_active_advisors_of_course(self):
        eligible = {self.provision(role=Role.ADVISOR).academic_id for _ in range(2)}
        self.provision(role=Role.ADVISOR, is_active=False)
        self.provision(role=Role.ADVISOR, course_id=uuid4())
        self.provision(role=Role.STUDENT)

        claims = self.decode(self.issue_token(self.provision(role=Role.COORDINATOR)))

        self.assertEqual(set(claims["assignable_advisor_ids"]), {str(value) for value in eligible})

    def test_coordinator_without_advisors_receives_empty_list(self):
        claims = self.decode(self.issue_token(self.provision(role=Role.COORDINATOR)))

        self.assertEqual(claims["assignable_advisor_ids"], [])

    def test_advisor_list_over_limit_fails_closed(self):
        for _ in range(2):
            self.provision(role=Role.ADVISOR)

        coordinator = self.provision(role=Role.COORDINATOR)

        with override_settings(IDENTITY_MAX_ASSIGNABLE_ADVISORS=1):
            self.assertEqual(self.login(coordinator.email).status_code, 403)

    def test_verifier_rejects_forged_and_altered_tokens(self):
        token = self.issue_token(self.provision())
        claims = self.decode(token)
        other_key = generate_key(3072)

        forged = {
            "other_key": jwt.encode(claims, other_key, algorithm="RS256", headers={"typ": "at+jwt"}),
            "wrong_type": jwt.encode(claims, self.key, algorithm="RS256", headers={"typ": "JWT"}),
            "unsigned": jwt.encode(claims, None, algorithm="none", headers={"typ": "at+jwt"}),
            "other_audience": jwt.encode(
                {**claims, "aud": "urn:other"}, self.key, algorithm="RS256", headers={"typ": "at+jwt"},
            ),
            "tampered": token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB"),
        }

        for case, value in forged.items():
            with self.subTest(case=case), self.assertRaises(InvalidAccessTokenError):
                self.verifier().verify(value)


class SigningKeyTests(SimpleTestCase):

    def test_rejects_weak_encrypted_or_invalid_keys(self):
        cases = {
            "weak": private_pem(generate_key(1024)),
            "encrypted": private_pem(generate_key(), b"secret-passphrase"),
            "garbage": "not a key",
        }

        for case, pem in cases.items():
            with self.subTest(case=case), self.assertRaises(ValueError):
                load_private_key(pem)

    def test_accepts_rsa_2048_key(self):
        self.assertEqual(load_private_key(private_pem(generate_key())).key_size, 2048)

    def test_export_command_prints_only_public_key(self):
        output = StringIO()

        with override_settings(
            IDENTITY_JWT_PRIVATE_KEY=private_pem(generate_key()),
            IDENTITY_JWT_ISSUER=TEST_ISSUER,
            IDENTITY_JWT_AUDIENCE=TEST_AUDIENCE,
        ):
            call_command("export_jwt_public_key", stdout=output)

        self.assertTrue(output.getvalue().startswith("-----BEGIN PUBLIC KEY-----"))
        self.assertNotIn("PRIVATE", output.getvalue())
