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

from confluent_kafka import Producer

from thesis.application.ports.event_publisher import (
    EventPublisherPort,
)

from thesis.adapters.outbound.messaging.kafka_event_publisher import (
    KafkaEventPublisher,
)

from thesis.application.use_case.create_thesis import (
    CreateThesisUseCase,
)

from thesis.adapters.outbound.persistence.django_outbox_repository import (
    DjangoOutboxRepository,
)

from thesis.adapters.outbound.persistence.django_unit_of_work import (
    DjangoUnitOfWork,
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

@lru_cache(maxsize=1)
def get_kafka_producer() -> Producer:

    return Producer({
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "client.id": "thesis-service",
        "enable.idempotence": True,
        "acks": "all",
    })


def build_event_publisher() -> EventPublisherPort:

    return KafkaEventPublisher(
        producer=get_kafka_producer(),
        topic=settings.KAFKA_THESIS_EVENTS_TOPIC,
    )

def build_create_thesis_use_case() -> CreateThesisUseCase:

    return CreateThesisUseCase(
        repository=DjangoThesisRepository(),
        outbox_repository=DjangoOutboxRepository(),
        unit_of_work=DjangoUnitOfWork(),
    )