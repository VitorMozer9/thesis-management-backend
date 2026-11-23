from unittest.mock import Mock
from uuid import uuid4

from django.test import TestCase

from thesis.application.exceptions import EventPublicationError

from thesis.application.ports.event_publisher import EventPublisherPort

from thesis.application.use_case.publish_outbox_events import (
    PublishOutboxEventsUseCase,
)

from thesis.domain.events.thesis_events import ThesisCreatedEvent

from thesis.adapters.outbound.persistence.outbox_models import (
    OutboxEventModel,
)

from thesis.adapters.outbound.persistence.django_outbox_repository import (
    DjangoOutboxRepository,
)

from thesis.adapters.outbound.persistence.django_outbox_dispatch import (
    DjangoOutboxDispatchRepository,
)


class PublishOutboxEventsTests(TestCase):

    def setUp(self):

        self.outbox_repository = DjangoOutboxRepository()
        self.dispatch_repository = DjangoOutboxDispatchRepository()

        self.publisher = Mock(spec=EventPublisherPort)

        self.use_case = PublishOutboxEventsUseCase(
            repository=self.dispatch_repository,
            publisher=self.publisher,
        )

    def create_pending_event(self):

        event = ThesisCreatedEvent(
            thesis_id=uuid4(),
        )

        self.outbox_repository.add(event)

        return event

    def test_publishes_pending_event(self):

        event = self.create_pending_event()

        result = self.use_case.execute()

        self.assertEqual(result.published, 1)
        self.assertEqual(result.failed, 0)

        self.publisher.publish.assert_called_once()

        published_event = self.publisher.publish.call_args.args[0]

        self.assertEqual(
            published_event.event_id,
            event.event_id,
        )

        self.assertEqual(
            published_event.thesis_id,
            event.thesis_id,
        )

        saved_event = OutboxEventModel.objects.get(
            id=event.event_id,
        )

        self.assertIsNotNone(saved_event.published_at)
        self.assertEqual(saved_event.attempts, 1)

    def test_keeps_event_pending_when_kafka_fails(self):

        event = self.create_pending_event()

        self.publisher.publish.side_effect = EventPublicationError(
            "Kafka unavailable."
        )

        result = self.use_case.execute()

        self.assertEqual(result.published, 0)
        self.assertEqual(result.failed, 1)

        saved_event = OutboxEventModel.objects.get(
            id=event.event_id,
        )

        self.assertIsNone(saved_event.published_at)
        self.assertEqual(saved_event.attempts, 1)

    def test_retries_event_with_same_id(self):

        event = self.create_pending_event()

        self.publisher.publish.side_effect = EventPublicationError(
            "Kafka unavailable."
        )

        self.use_case.execute()

        self.publisher.publish.side_effect = None

        result = self.use_case.execute()

        self.assertEqual(result.published, 1)

        self.assertEqual(
            self.publisher.publish.call_count,
            2,
        )

        first_event = self.publisher.publish.call_args_list[0].args[0]
        second_event = self.publisher.publish.call_args_list[1].args[0]

        self.assertEqual(
            first_event.event_id,
            second_event.event_id,
        )

        self.assertEqual(second_event.event_id, event.event_id)

        saved_event = OutboxEventModel.objects.get(
            id=event.event_id,
        )

        self.assertIsNotNone(saved_event.published_at)
        self.assertEqual(saved_event.attempts, 2)

    def test_does_not_publish_without_pending_events(self):

        result = self.use_case.execute()

        self.assertEqual(result.published, 0)
        self.assertEqual(result.failed, 0)

        self.publisher.publish.assert_not_called()