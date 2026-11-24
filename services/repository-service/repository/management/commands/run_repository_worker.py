import logging
import signal

from confluent_kafka import Consumer, KafkaException
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from config.dependencies import service
from repository.adapters.events import consume


class Command(BaseCommand):
    def handle(self, *args, **options):
        running = True

        def stop(*args):
            nonlocal running
            running = False

        signal.signal(signal.SIGTERM, stop)
        consumer = Consumer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS, "group.id": settings.KAFKA_GROUP,
            "auto.offset.reset": "earliest", "enable.auto.commit": False, "enable.auto.offset.store": False,
        })
        try:
            consumer.subscribe([settings.KAFKA_TOPIC])
            handler = service()
            while running:
                message = consumer.poll(1)
                if message is None:
                    continue
                if message.error():
                    raise KafkaException(message.error())
                close_old_connections()
                if consume(message, consumer, handler):
                    logging.warning("Evento em quarentena. Partição %s, offset %s.", message.partition(), message.offset())
        except KeyboardInterrupt:
            pass
        except Exception:
            raise CommandError("Consumo interrompido. Verifique banco, volume e broker antes de reiniciar.") from None
        finally:
            consumer.close()
