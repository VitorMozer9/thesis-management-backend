import signal
from threading import Event

from confluent_kafka import Consumer
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from config.dependencies import build_process_submitted_pdf_use_case
from thesis.adapters.inbound.kafka_pdf_consumer import PdfConsumerError, PdfEventConsumer


class Command(BaseCommand):
    help = "Consome submissões e persiste o resultado da extração do PDF."

    def handle(self, *args, **options):
        processor = build_process_submitted_pdf_use_case()
        consumer = Consumer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "group.id": settings.KAFKA_PDF_GROUP_ID,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "earliest",
        })
        worker = PdfEventConsumer(consumer, processor)
        stopping = Event()

        def stop(signum, frame):
            stopping.set()

        previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            consumer.subscribe([settings.KAFKA_THESIS_EVENTS_TOPIC])
            self.stdout.write("Consumidor de PDFs iniciado.")
            while not stopping.is_set():
                close_old_connections()
                worker.poll_once()
        except PdfConsumerError as exc:
            raise CommandError(str(exc)) from None
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            consumer.close()
