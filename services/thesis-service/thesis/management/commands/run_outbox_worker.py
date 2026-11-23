import logging
import signal

from threading import Event

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections

from config.dependencies import build_event_publisher

from thesis.application.use_case.publish_outbox_events import (
    PublishOutboxEventsUseCase,
)

from thesis.adapters.outbound.persistence.django_outbox_dispatch import (
    DjangoOutboxDispatchRepository,
)


logger = logging.getLogger(__name__)


class Command(BaseCommand):

    help = "Continuously publishes pending outbox events to Kafka."

    def add_arguments(self, parser):

        parser.add_argument(
            "--interval",
            type=float,
            default=5.0,
            help="Polling interval in seconds.",
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Maximum events per processing cycle.",
        )

        parser.add_argument(
            "--once",
            action="store_true",
            help="Run one processing cycle and exit.",
        )

    def handle(self, *args, **options):

        interval = options["interval"]
        limit = options["limit"]
        run_once = options["once"]

        if interval <= 0:
            raise CommandError(
                "The interval must be greater than zero."
            )

        if limit <= 0:
            raise CommandError(
                "The limit must be greater than zero."
            )

        stop_requested = Event()

        def request_shutdown(signum, frame):
            stop_requested.set()

        previous_sigint = signal.getsignal(signal.SIGINT)
        previous_sigterm = signal.getsignal(signal.SIGTERM)

        use_case = PublishOutboxEventsUseCase(
            repository=DjangoOutboxDispatchRepository(),
            publisher=build_event_publisher(),
        )

        try:
            signal.signal(signal.SIGINT, request_shutdown)
            signal.signal(signal.SIGTERM, request_shutdown)

            self.stdout.write(
                self.style.SUCCESS("Outbox worker started.")
            )

            while not stop_requested.is_set():

                close_old_connections()

                try:
                    result = use_case.execute(limit=limit)

                    if result.published > 0 or result.failed > 0:
                        self.stdout.write(
                            f"Published: {result.published} | "
                            f"Failed: {result.failed}"
                        )

                    if run_once and result.failed > 0:
                        raise CommandError(
                            "Kafka publication failed. "
                            "Events remain pending."
                        )

                except DatabaseError as exc:

                    logger.exception(
                        "Database error while processing outbox."
                    )

                    if run_once:
                        raise CommandError(
                            "Outbox database operation failed."
                        ) from exc

                finally:
                    close_old_connections()

                if run_once:
                    break

                stop_requested.wait(interval)

        finally:
            signal.signal(signal.SIGINT, previous_sigint)
            signal.signal(signal.SIGTERM, previous_sigterm)

            close_old_connections()

            self.stdout.write("Outbox worker stopped.")