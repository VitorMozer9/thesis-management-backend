from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from thesis.application.use_case.publish_outbox_events import (
    PublishOutboxResult,
)


class OutboxWorkerTests(SimpleTestCase):

    @patch(
        "thesis.management.commands.run_outbox_worker."
        "build_event_publisher"
    )
    @patch(
        "thesis.management.commands.run_outbox_worker."
        "DjangoOutboxDispatchRepository"
    )
    @patch(
        "thesis.management.commands.run_outbox_worker."
        "PublishOutboxEventsUseCase"
    )
    def test_executes_one_processing_cycle(
        self,
        mock_use_case_class,
        mock_repository_class,
        mock_publisher_builder,
    ):

        mock_use_case = mock_use_case_class.return_value

        mock_use_case.execute.return_value = PublishOutboxResult(
            published=1,
            failed=0,
        )

        output = StringIO()

        call_command(
            "run_outbox_worker",
            once=True,
            limit=5,
            interval=0.1,
            stdout=output,
        )

        mock_use_case.execute.assert_called_once_with(
            limit=5
        )

        self.assertIn(
            "Published: 1 | Failed: 0",
            output.getvalue(),
        )

    def test_rejects_invalid_interval(self):

        with self.assertRaises(CommandError):

            call_command(
                "run_outbox_worker",
                once=True,
                interval=0,
            )