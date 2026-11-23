from uuid import uuid4

from django.test import TestCase

from thesis.domain.events.thesis_events import (
    ThesisCreatedEvent,
)

from thesis.adapters.outbound.persistence.outbox_models import (
    OutboxEventModel,
)

from thesis.adapters.outbound.persistence.django_outbox_repository import (
    DjangoOutboxRepository,
)

from thesis.adapters.outbound.persistence.django_unit_of_work import (
    DjangoUnitOfWork,
)


class OutboxRepositoryTests(TestCase):

    def setUp(self):

        self.repository = DjangoOutboxRepository()
        self.unit_of_work = DjangoUnitOfWork()

    def test_saves_event_in_outbox(self):

        event = ThesisCreatedEvent(
            thesis_id=uuid4()
        )

        self.repository.add(event)

        saved_event = OutboxEventModel.objects.get(
            id=event.event_id
        )

        self.assertEqual(
            saved_event.event_type,
            "thesis.created",
        )

        self.assertEqual(
            saved_event.aggregate_id,
            event.thesis_id,
        )

        self.assertIsNone(
            saved_event.published_at
        )

    def test_rolls_back_event_when_transaction_fails(self):

        event = ThesisCreatedEvent(
            thesis_id=uuid4()
        )

        with self.assertRaises(RuntimeError):

            with self.unit_of_work.transaction():

                self.repository.add(event)

                raise RuntimeError(
                    "Simulated transaction failure."
                )

        event_exists = OutboxEventModel.objects.filter(
            id=event.event_id
        ).exists()

        self.assertFalse(event_exists)