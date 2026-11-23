import os

from concurrent.futures import ThreadPoolExecutor
from time import sleep
from uuid import uuid4

from django.test import SimpleTestCase
from redis import Redis
from redis.exceptions import RedisError

from thesis.adapters.outbound.redis.redis_rate_limit import RedisRateLimit
from thesis.application.ports.rate_limit import RateLimitExceeded


REDIS_TEST_URL = os.environ.get("REDIS_TEST_URL", "redis://127.0.0.1:6379/15")


class RedisRateLimitTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.redis_client = Redis.from_url(REDIS_TEST_URL, decode_responses=True)
        cls.redis_client.ping()

    @classmethod
    def tearDownClass(cls):
        cls.redis_client.close()
        super().tearDownClass()

    def setUp(self):
        self.account_id = uuid4()
        self.limiter = self.build_limiter("upload", limit=3, window_seconds=60)

    def build_limiter(self, operation, limit, window_seconds, client=None):
        limiter = RedisRateLimit(client or self.redis_client, f"test-{uuid4().hex}-{operation}", limit, window_seconds)

        self.addCleanup(self.redis_client.delete, limiter.key(self.account_id))

        return limiter

    def consume_times(self, limiter, account_id, times):
        for _ in range(times):
            limiter.consume(account_id)

    def test_rejects_after_quota_with_retry_after(self):
        self.consume_times(self.limiter, self.account_id, 3)

        with self.assertRaises(RateLimitExceeded) as raised:
            self.limiter.consume(self.account_id)

        self.assertGreaterEqual(raised.exception.retry_after, 1)
        self.assertLessEqual(raised.exception.retry_after, 60)

    def test_rejected_requests_do_not_extend_counter(self):
        self.consume_times(self.limiter, self.account_id, 3)

        for _ in range(5):
            with self.assertRaises(RateLimitExceeded):
                self.limiter.consume(self.account_id)

        self.assertEqual(self.redis_client.get(self.limiter.key(self.account_id)), "3")

    def test_quota_is_isolated_per_account(self):
        other_account = uuid4()
        self.addCleanup(self.redis_client.delete, self.limiter.key(other_account))

        self.consume_times(self.limiter, self.account_id, 3)
        self.consume_times(self.limiter, other_account, 3)

        with self.assertRaises(RateLimitExceeded):
            self.limiter.consume(other_account)

    def test_quota_is_isolated_per_operation(self):
        submit_limiter = self.build_limiter("submit", limit=1, window_seconds=60)

        self.consume_times(self.limiter, self.account_id, 3)
        submit_limiter.consume(self.account_id)

        with self.assertRaises(RateLimitExceeded):
            submit_limiter.consume(self.account_id)

    def test_quota_is_restored_after_window_expires(self):
        limiter = self.build_limiter("upload", limit=1, window_seconds=1)
        limiter.consume(self.account_id)

        with self.assertRaises(RateLimitExceeded):
            limiter.consume(self.account_id)

        sleep(1.2)

        limiter.consume(self.account_id)

    def test_counter_without_expiration_is_repaired(self):
        key = self.limiter.key(self.account_id)
        self.redis_client.set(key, 3)

        with self.assertRaises(RateLimitExceeded):
            self.limiter.consume(self.account_id)

        self.assertGreater(self.redis_client.ttl(key), 0)

    def test_concurrent_requests_never_exceed_quota(self):
        limiter = self.build_limiter("upload", limit=5, window_seconds=60)
        clients = [Redis.from_url(REDIS_TEST_URL, decode_responses=True) for _ in range(30)]

        for client in clients:
            self.addCleanup(client.close)

        def attempt(client):
            try:
                RedisRateLimit(client, limiter.operation, 5, 60).consume(self.account_id)
                return True

            except RateLimitExceeded:
                return False

        with ThreadPoolExecutor(max_workers=15) as executor:
            results = list(executor.map(attempt, clients))

        self.assertEqual(results.count(True), 5)
        self.assertEqual(self.redis_client.get(limiter.key(self.account_id)), "5")

    def test_redis_failure_is_propagated(self):
        unavailable = Redis(host="127.0.0.1", port=1, socket_connect_timeout=0.2)
        limiter = RedisRateLimit(unavailable, "upload", 3, 60)

        with self.assertRaises(RedisError):
            limiter.consume(self.account_id)

    def test_rejects_non_positive_configuration(self):
        for limit, window in ((0, 60), (1, 0)):
            with self.subTest(limit=limit, window=window), self.assertRaises(ValueError):
                RedisRateLimit(self.redis_client, "upload", limit, window)
