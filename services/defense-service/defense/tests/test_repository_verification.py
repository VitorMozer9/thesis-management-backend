from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from defense.adapters.outbound.models import Defense


class CompletionVerificationTests(TestCase):
    def test_only_machine_credential_can_verify_closed_result(self):
        start = datetime(2024, 12, 31, 20, tzinfo=timezone.utc)
        row = Defense.objects.create(thesis_id=uuid4(), course_id=uuid4(), student_id=uuid4(), advisor_id=uuid4(),
                                     starts_at=start, ends_at=start + timedelta(hours=1))
        url = f"/internal/completed-defenses/{row.id}/"
        client = APIClient()
        key = token_urlsafe(48)
        with self.settings(REPOSITORY_VERIFICATION_KEY=key):
            self.assertEqual(client.get(url).status_code, 403)
            client.credentials(HTTP_AUTHORIZATION="Bearer inválido")
            self.assertEqual(client.get(url).status_code, 403)
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {key}")
            self.assertEqual(client.get(url).status_code, 404)
            row.status, row.result = "held", "approved"
            row.save()
            self.assertEqual(client.get(url).json(), {
                "thesis_id": str(row.thesis_id), "course_id": str(row.course_id), "defense_id": str(row.id),
                "result": "approved", "defense_year": 2024,
            })
        with self.settings(REPOSITORY_VERIFICATION_KEY=""):
            self.assertEqual(client.get(url).status_code, 403)
