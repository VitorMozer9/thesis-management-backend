from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from uuid import UUID

from redis import Redis

from thesis.application.ports.thesis_lock import (
    ThesisAlreadyLockedError,
    ThesisLockPort,
)


class RedisThesisLockAdapter(ThesisLockPort):

    def __init__(
        self,
        redis_client: Redis,
        lock_timeout_seconds: int = 300
    ):
        if lock_timeout_seconds <= 0:
            raise ValueError("Lock timeout must be positive.")

        self._redis = redis_client
        self._lock_timeout_seconds = lock_timeout_seconds

    def lock(
        self,
        thesis_id: UUID
    ) -> AbstractContextManager[None]:
        return self._acquire_lock(thesis_id)

    @contextmanager
    def _acquire_lock(
        self,
        thesis_id: UUID
    ) -> Iterator[None]:

        lock_key = f"thesis:{thesis_id}:lock"

        redis_lock = self._redis.lock(
            name=lock_key,
            timeout=self._lock_timeout_seconds,
            blocking=False
        )

        acquired = redis_lock.acquire(blocking=False)

        if not acquired:
            raise ThesisAlreadyLockedError(
                f"Thesis {thesis_id} is already being modified."
            )

        try:
            yield
        finally:
            redis_lock.release()