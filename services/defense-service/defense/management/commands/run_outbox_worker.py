import json
from time import sleep

from confluent_kafka import KafkaException, Producer
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.db.models import F
from django.utils import timezone

from defense.adapters.outbound.models import Outbox


def publish_next(producer):
    with transaction.atomic():
        event = (Outbox.objects.select_for_update(skip_locked=True).filter(published_at=None)
                 .order_by("attempts", "occurred_at", "id").first())
        if event is None:
            return False

        failed = []
        value = json.dumps({
            "event_id": str(event.id), "event_type": event.event_type, "version": 1,
            "occurred_at": event.occurred_at.isoformat(), "aggregate_id": str(event.defense_id),
            "data": event.data,
        }).encode()
        try:
            producer.produce(settings.KAFKA_TOPIC, key=str(event.defense_id), value=value,
                             on_delivery=lambda error, message: failed.append(error))
            delivered = producer.flush(5) == 0 and failed == [None]
        except (KafkaException, BufferError):
            delivered = False

        fields = {"attempts": F("attempts") + 1}
        if delivered:
            fields["published_at"] = timezone.now()
        Outbox.objects.filter(pk=event.pk).update(**fields)
        return delivered


class Command(BaseCommand):
    def handle(self, *args, **options):
        producer = Producer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS, "enable.idempotence": True,
            "message.timeout.ms": 4000,
        })
        try:
            while True:
                close_old_connections()
                if not publish_next(producer):
                    sleep(2)
        except KeyboardInterrupt:
            return
