import json

from uuid import uuid4

from django.test import TestCase

from thesis.adapters.outbound.persistence.models import ThesisModel


class ThesisApiTests(TestCase):

    def setUp(self):
        self.payload = {
            "title": "Hexagonal Architecture",
            "abstract": "A study about hexagonal architecture.",
            "student_id": str(uuid4()),
            "course_id": str(uuid4()),
        }

    def test_create_thesis(self):
        response = self.client.post(
            "/api/theses/",
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)

        self.assertEqual(
            ThesisModel.objects.count(),
            1,
        )

    def test_get_existing_thesis(self):
        created = self.client.post(
            "/api/theses/",
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        thesis_id = created.json()["id"]

        response = self.client.get(
            f"/api/theses/{thesis_id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], thesis_id)

    def test_get_nonexistent_thesis(self):
        response = self.client.get(
            f"/api/theses/{uuid4()}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_update_thesis(self):
        created = self.client.post(
            "/api/theses/",
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        thesis_id = created.json()["id"]

        response = self.client.patch(
            f"/api/theses/{thesis_id}/",
            data=json.dumps({
                "title": "Updated Thesis Title"
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        thesis = ThesisModel.objects.get(id=thesis_id)

        self.assertEqual(
            thesis.title,
            "Updated Thesis Title",
        )

    def test_reject_empty_title(self):
        created = self.client.post(
            "/api/theses/",
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        thesis_id = created.json()["id"]

        response = self.client.patch(
            f"/api/theses/{thesis_id}/",
            data=json.dumps({
                "title": ""
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)