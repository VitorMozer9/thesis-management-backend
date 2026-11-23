from functools import lru_cache
from pathlib import Path

from django.conf import settings
from redis import Redis

from thesis.adapters.outbound.persistence.django_audit import DjangoAudit
from thesis.adapters.outbound.persistence.pdf_extraction import DjangoExtractionRepository
from thesis.adapters.outbound.storage.pdf_text import PypdfTextExtractor
from thesis.application.use_case.process_submitted_pdf import ProcessSubmittedPdfUseCase
from thesis.application.identity import AcademicIdentity
from thesis.application.use_case.get_thesis import GetThesisUseCase
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

from thesis.adapters.outbound.redis.redis_rate_limit import RedisRateLimit
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

from thesis.application.use_case.delete_thesis import DeleteThesisUseCase
from thesis.application.use_case.list_theses import ListThesesUseCase
from thesis.application.use_case.review_thesis import ReviewThesisUseCase
from thesis.application.use_case.submit_thesis import (
    SubmitThesisUseCase,
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


def build_update_thesis_use_case(actor: AcademicIdentity) -> UpdateThesisUseCase:

    redis_client = get_redis_client()

    return UpdateThesisUseCase(
        actor=actor,
        unit_of_work=DjangoUnitOfWork(),
        audit=DjangoAudit(),
        repository=DjangoThesisRepository(actor),
        thesis_lock=RedisThesisLockAdapter(redis_client),
    )


def build_upload_thesis_pdf_use_case(actor: AcademicIdentity) -> UploadThesisPdfUseCase:

    redis_client = get_redis_client()

    return UploadThesisPdfUseCase(
        rate_limit=RedisRateLimit(
            redis_client, "upload", settings.THESIS_UPLOAD_LIMIT, settings.THESIS_RATE_WINDOW_SECONDS,
        ),
        actor=actor,
        unit_of_work=DjangoUnitOfWork(),
        audit=DjangoAudit(),
        repository=DjangoThesisRepository(actor),
        storage=LocalFileStorage(
            Path(settings.MEDIA_ROOT)
        ),
        thesis_lock=RedisThesisLockAdapter(redis_client),
        processing=RedisUploadProcessingAdapter(redis_client),
    )

def build_get_thesis_upload_status_use_case(actor: AcademicIdentity | None) -> GetThesisUploadStatusUseCase:

    redis_client = get_redis_client()

    return GetThesisUploadStatusUseCase(
        repository=DjangoThesisRepository(actor),
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

def build_create_thesis_use_case(actor: AcademicIdentity) -> CreateThesisUseCase:

    return CreateThesisUseCase(
        actor=actor,
        audit=DjangoAudit(),
        repository=DjangoThesisRepository(actor),
        outbox_repository=DjangoOutboxRepository(),
        unit_of_work=DjangoUnitOfWork(),
    )

def build_submit_thesis_use_case(actor: AcademicIdentity) -> SubmitThesisUseCase:

    return SubmitThesisUseCase(
        rate_limit=RedisRateLimit(
            get_redis_client(), "submit", settings.THESIS_SUBMIT_LIMIT, settings.THESIS_RATE_WINDOW_SECONDS,
        ),
        extractions=DjangoExtractionRepository(),
        actor=actor,
        audit=DjangoAudit(),
        repository=DjangoThesisRepository(actor),
        thesis_lock=RedisThesisLockAdapter(get_redis_client()),
        outbox_repository=DjangoOutboxRepository(),
        unit_of_work=DjangoUnitOfWork(),
    )


def build_review_thesis_use_case(actor: AcademicIdentity) -> ReviewThesisUseCase:
    return ReviewThesisUseCase(
        actor=actor,
        audit=DjangoAudit(),
        repository=DjangoThesisRepository(actor),
        thesis_lock=RedisThesisLockAdapter(get_redis_client()),
        outbox_repository=DjangoOutboxRepository(),
        unit_of_work=DjangoUnitOfWork(),
    )


def build_list_theses_use_case(actor: AcademicIdentity | None) -> ListThesesUseCase:

    return ListThesesUseCase(repository=DjangoThesisRepository(actor))


def build_delete_thesis_use_case(actor: AcademicIdentity) -> DeleteThesisUseCase:

    return DeleteThesisUseCase(
        actor=actor,
        audit=DjangoAudit(),
        repository=DjangoThesisRepository(actor),
        thesis_lock=RedisThesisLockAdapter(get_redis_client()),
        unit_of_work=DjangoUnitOfWork(),
    )


def build_get_thesis_use_case(actor: AcademicIdentity) -> GetThesisUseCase:
    return GetThesisUseCase(repository=DjangoThesisRepository(actor))


def build_process_submitted_pdf_use_case() -> ProcessSubmittedPdfUseCase:
    return ProcessSubmittedPdfUseCase(
        repository=DjangoExtractionRepository(),
        storage=LocalFileStorage(Path(settings.MEDIA_ROOT)),
        extractor=PypdfTextExtractor(),
        unit_of_work=DjangoUnitOfWork(),
    )
