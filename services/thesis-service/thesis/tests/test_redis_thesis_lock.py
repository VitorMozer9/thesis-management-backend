import os

from uuid import uuid4

from django.test import SimpleTestCase
from redis import Redis

from thesis.application.ports.thesis_lock import (
    ThesisAlreadyLockedError,
)

from thesis.adapters.outbound.redis.redis_thesis_lock import (
    RedisThesisLockAdapter,
)


class RedisThesisLockTests(SimpleTestCase):

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

        self.adapter = RedisThesisLockAdapter(
            redis_client=self.redis_client,
            lock_timeout_seconds=30,
        )

    def test_can_acquire_available_lock(self):

        with self.adapter.lock(self.thesis_id):
            pass

    def test_cannot_acquire_existing_lock(self):

        with self.adapter.lock(self.thesis_id):

            with self.assertRaises(
                ThesisAlreadyLockedError
            ):

                with self.adapter.lock(self.thesis_id):
                    pass

    def test_releases_lock_after_exception(self):

        with self.assertRaises(ValueError):

            with self.adapter.lock(self.thesis_id):
                raise ValueError("Simulated error.")

        with self.adapter.lock(self.thesis_id):
            pass

    def test_different_theses_can_be_locked(self):

        another_thesis_id = uuid4()

        with self.adapter.lock(self.thesis_id):

            with self.adapter.lock(another_thesis_id):
                pass