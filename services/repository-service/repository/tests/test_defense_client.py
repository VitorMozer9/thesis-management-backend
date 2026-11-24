import json
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import uuid4

from repository.adapters.defenses import DefenseClient
from repository.adapters.events import decode
from repository.domain import Conflict, Unavailable


class DefenseClientTests(TestCase):
    def setUp(self):
        defense_id = str(uuid4())
        self.data = {"defense_id": defense_id, "thesis_id": str(uuid4()), "course_id": str(uuid4()), "result": "approved"}
        envelope = {"event_id": str(uuid4()), "aggregate_id": defense_id, "occurred_at": "2026-01-01T01:00:00Z",
                    "version": 1, "event_type": "defense.completed", "data": self.data}
        self.event = decode(json.dumps(envelope).encode())
        self.client = DefenseClient("http://defense-api:8000", "x" * 32)
        opener = self.enterContext(patch("repository.adapters.defenses.build_opener"))
        self.request = opener.return_value.open

    def test_year_and_result_from_authority(self):
        self.request.return_value = BytesIO(json.dumps(dict(self.data, defense_year=2025)).encode())
        self.assertEqual(self.client.verify(self.event), 2025)
        self.request.return_value = BytesIO(json.dumps(dict(self.data, result="rejected", defense_year=2025)).encode())
        with self.assertRaises(Conflict):
            self.client.verify(self.event)

    def test_missing_or_transient_verification(self):
        self.request.side_effect = HTTPError("http://defense-api", 404, "missing", {}, None)
        with self.assertRaises(Conflict):
            self.client.verify(self.event)
        self.request.side_effect = HTTPError("http://defense-api", 503, "unavailable", {}, None)
        with self.assertRaises(Unavailable):
            self.client.verify(self.event)
