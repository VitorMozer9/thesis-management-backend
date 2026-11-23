import json
import os
import subprocess
import sys

from pathlib import Path
from unittest import skipUnless

from identity.domain.account import Role
from identity.tests.support import (
    TEST_AUDIENCE,
    TEST_ISSUER,
    IdentityTestCase,
    generate_key,
    public_pem,
)


THESIS_SERVICE_DIR = Path(__file__).resolve().parents[3] / "thesis-service"

VERIFY_WITH_THESIS_SERVICE = """
import json
import sys

import django

django.setup()

from django.test import RequestFactory
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from thesis.adapters.inbound.rest.authentication import AcademicTokenAuthentication

results = []

for token in json.load(sys.stdin):
    request = Request(RequestFactory().get("/api/theses/", HTTP_AUTHORIZATION=f"Bearer {token}"))

    try:
        identity, _ = AcademicTokenAuthentication().authenticate(request)

    except AuthenticationFailed:
        results.append(None)
        continue

    results.append({
        "account_id": str(identity.account_id),
        "role": identity.role.value,
        "academic_id": str(identity.academic_id),
        "course_id": str(identity.course_id),
        "assignable_advisors": sorted(str(value) for value in identity.assignable_advisors),
    })

print(json.dumps(results))
"""


@skipUnless(THESIS_SERVICE_DIR.joinpath("manage.py").exists(), "Requer o código do thesis-service no repositório.")
class ThesisServiceCompatibilityTests(IdentityTestCase):

    def verify_with_thesis_service(self, tokens, public_key=None):
        environment = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "THESIS_JWT_PUBLIC_KEY": public_key or public_pem(self.key),
            "THESIS_JWT_ISSUER": TEST_ISSUER,
            "THESIS_JWT_AUDIENCE": TEST_AUDIENCE,
            "THESIS_JWT_PUBLIC_KEY_FILE": "",
        }

        completed = subprocess.run(
            [sys.executable, "-c", VERIFY_WITH_THESIS_SERVICE],
            cwd=THESIS_SERVICE_DIR,
            env=environment,
            input=json.dumps(tokens),
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)

        return json.loads(completed.stdout.strip().splitlines()[-1])

    def test_thesis_service_accepts_issued_tokens(self):
        advisor = self.provision(role=Role.ADVISOR)
        student = self.provision(role=Role.STUDENT)
        coordinator = self.provision(role=Role.COORDINATOR)

        identities = self.verify_with_thesis_service([self.issue_token(student), self.issue_token(coordinator)])

        self.assertEqual(identities[0], {
            "account_id": str(student.id),
            "role": "student",
            "academic_id": str(student.academic_id),
            "course_id": str(self.course_id),
            "assignable_advisors": [],
        })
        self.assertEqual(identities[1]["role"], "coordinator")
        self.assertEqual(identities[1]["assignable_advisors"], [str(advisor.academic_id)])

    def test_thesis_service_rejects_tokens_from_untrusted_key(self):
        token = self.issue_token(self.provision())

        self.assertEqual(self.verify_with_thesis_service([token], public_pem(generate_key(3072))), [None])
