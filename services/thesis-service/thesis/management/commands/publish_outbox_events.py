from django.core.management.base import BaseCommand, CommandError

from config.dependencies import build_event_publisher

from thesis.application.use_case.publish_outbox_events import (
    PublishOutboxEventsUseCase,
)

from thesis.adapters.outbound.persistence.django_outbox_dispatch import (
    DjangoOutboxDispatchRepository,
)


class Command(BaseCommand):

    help = "Publishes pending thesis outbox events to Kafka."

    def add_arguments(self, parser):

        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Maximum number of events to process.",
        )

    def handle(self, *args, **options):

        limit = options["limit"]

        if limit < 1:
            raise CommandError(
                "The --limit argument must be greater than zero."
            )

        use_case = PublishOutboxEventsUseCase(
            repository=DjangoOutboxDispatchRepository(),
            publisher=build_event_publisher(),
        )

        result = use_case.execute(limit=limit)

        self.stdout.write(
            f"Published: {result.published} | Failed: {result.failed}"
        )

        if result.failed:
            raise CommandError(
                "Kafka publication failed. "
                "The event remains pending for a future retry."
            )