from functools import lru_cache
from pathlib import Path

from django.conf import settings
from redis import Redis

from thesis.application.use_case.update_thesis import (
    UpdateThesisUseCase,
)

from thesis.application.use_case.upload_thesis_pdf import (
    UploadThesisPdfUseCase,
)

from thesis.adapters.outbound.persistence.django_thesis_repository import (
    DjangoThesisRepository,
)

from thesis.adapters.outbound.storage.local_file_storage import (
    LocalFileStorage,
)

from thesis.adapters.outbound.redis.redis_thesis_lock import (
    RedisThesisLockAdapter,
)

from thesis.adapters.outbound.redis.redis_upload_processing import (
    RedisUploadProcessingAdapter,
)

from thesis.application.use_case.get_thesis_upload_status import (
    GetThesisUploadStatusUseCase,
)

@lru_cache(maxsize=1)
def get_redis_client() -> Redis:

    return Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=5,
    )


def build_update_thesis_use_case() -> UpdateThesisUseCase:

    redis_client = get_redis_client()

    return UpdateThesisUseCase(
        repository=DjangoThesisRepository(),
        thesis_lock=RedisThesisLockAdapter(redis_client),
    )


def build_upload_thesis_pdf_use_case() -> UploadThesisPdfUseCase:

    redis_client = get_redis_client()

    return UploadThesisPdfUseCase(
        repository=DjangoThesisRepository(),
        storage=LocalFileStorage(
            Path(settings.MEDIA_ROOT)
        ),
        thesis_lock=RedisThesisLockAdapter(redis_client),
        processing=RedisUploadProcessingAdapter(redis_client),
    )

def build_get_thesis_upload_status_use_case() -> GetThesisUploadStatusUseCase:

    redis_client = get_redis_client()

    return GetThesisUploadStatusUseCase(
        repository=DjangoThesisRepository(),
        processing=RedisUploadProcessingAdapter(redis_client),
    )