from uuid import UUID

from redis import Redis

from thesis.application.ports.upload_processing import (
    UploadProcessingPort,
    UploadProcessingStatus,
)

class RedisUploadProcessingAdapter(UploadProcessingPort):

    def __init__(
        self,
        redis_client: Redis,
        status_ttl_seconds: int = 3600
    ):
        if status_ttl_seconds <= 0:
            raise ValueError("Status TTL must be positive.")

        self._redis = redis_client
        self._status_ttl_seconds = status_ttl_seconds

    def set_status(
        self,
        thesis_id: UUID,
        status: UploadProcessingStatus
    ) -> None:

        key = f"thesis:{thesis_id}:upload:status"

        self._redis.set(
            name=key,
            value=status.value,
            ex=self._status_ttl_seconds
        )

    def get_status(
        self,
        thesis_id: UUID
    ) -> UploadProcessingStatus | None:

        key = f"thesis:{thesis_id}:upload:status"

        value = self._redis.get(key)

        if value is None:
            return None

        if isinstance(value, bytes):
            value = value.decode("utf-8")

        return UploadProcessingStatus(value)