import os

from uuid import uuid4

from django.test import SimpleTestCase
from redis import Redis

from thesis.application.ports.upload_processing import (
    UploadProcessingStatus,
)

from thesis.adapters.outbound.redis.redis_upload_processing import (
    RedisUploadProcessingAdapter,
)


class RedisUploadProcessingTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        redis_url = os.environ.get(
            "REDIS_TEST_URL",
            "redis://127.0.0.1:6379/15",
        )

        cls.redis_client = Redis.from_url(
            redis_url,
            decode_responses=True,
        )

        cls.redis_client.ping()

    @classmethod
    def tearDownClass(cls):
        cls.redis_client.close()
        super().tearDownClass()

    def setUp(self):

        self.thesis_id = uuid4()

        self.adapter = RedisUploadProcessingAdapter(
            redis_client=self.redis_client,
            status_ttl_seconds=60,
        )

        self.addCleanup(
            self.redis_client.delete,
            f"thesis:{self.thesis_id}:upload:status",
        )

    def test_returns_none_when_status_does_not_exist(self):

        result = self.adapter.get_status(
            self.thesis_id
        )

        self.assertIsNone(result)

    def test_saves_processing_status(self):

        self.adapter.set_status(
            self.thesis_id,
            UploadProcessingStatus.PROCESSING,
        )

        result = self.adapter.get_status(
            self.thesis_id
        )

        self.assertEqual(
            result,
            UploadProcessingStatus.PROCESSING,
        )

    def test_updates_processing_status(self):

        self.adapter.set_status(
            self.thesis_id,
            UploadProcessingStatus.PROCESSING,
        )

        self.adapter.set_status(
            self.thesis_id,
            UploadProcessingStatus.COMPLETED,
        )

        result = self.adapter.get_status(
            self.thesis_id
        )

        self.assertEqual(
            result,
            UploadProcessingStatus.COMPLETED,
        )

    def test_sets_expiration_time(self):

        self.adapter.set_status(
            self.thesis_id,
            UploadProcessingStatus.PROCESSING,
        )

        key = f"thesis:{self.thesis_id}:upload:status"

        ttl = self.redis_client.ttl(key)

        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 60)