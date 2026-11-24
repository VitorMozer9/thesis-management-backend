import signal
from time import sleep

from confluent_kafka import Consumer, KafkaException
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from config.dependencies import processor
from notifications.adapters.events import consume


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("mode", choices=["kafka", "delivery"])

    def handle(self, *args, **options):
        running = True

        def stop(*args):
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, stop)
        consumer = None
        try:
            if options["mode"] == "kafka":
                consumer = Consumer({
                    "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS, "group.id": settings.KAFKA_GROUP,
                    "auto.offset.reset": settings.KAFKA_OFFSET_RESET, "enable.auto.commit": False,
                    "enable.auto.offset.store": False,
                })
                consumer.subscribe(list(settings.TOPICS.values()))
            handler = processor()

            while running:
                close_old_connections()
                if consumer is not None:
                    message = consumer.poll(1)
                    if message is not None:
                        if message.error():
                            raise KafkaException(message.error())
                        consume(consumer, message)
                else:
                    expanded = handler.run_next("events")
                    delivered = handler.run_next("notifications")
                    if not (expanded or delivered):
                        sleep(1)
        except KeyboardInterrupt:
            pass
        except Exception:
            raise CommandError("Worker interrompido. Verifique PostgreSQL, configuração e broker.") from None
        finally:
            if consumer is not None:
                consumer.close()
