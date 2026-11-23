import json

from confluent_kafka import Producer, KafkaException

from thesis.application.exceptions import EventPublicationError

from thesis.application.ports.event_publisher import (
    EventPublisherPort,
)

from thesis.domain.events.thesis_events import (
    ThesisCreatedEvent,
)


class KafkaEventPublisher(EventPublisherPort):

    def __init__(
        self,
        producer: Producer,
        topic: str,
        delivery_timeout_seconds: float = 10.0,
    ):

        self._producer = producer
        self._topic = topic
        self._delivery_timeout_seconds = delivery_timeout_seconds

    def publish(
        self,
        event: ThesisCreatedEvent
    ) -> None:

        message = {
            "event_id": str(event.event_id),
            "event_type": event.event_type,
            "version": event.version,
            "occurred_at": event.occurred_at.isoformat(),
            "aggregate_id": str(event.thesis_id),
            "data": {
                "thesis_id": str(event.thesis_id),
            },
        }

        message_bytes = json.dumps(message,ensure_ascii=False,).encode("utf-8")

        delivery_errors = []

        def on_delivery(error, message):

            if error is not None:
                delivery_errors.append(str(error))

        try:

            self._producer.produce(
                topic=self._topic,
                key=str(event.thesis_id),
                value=message_bytes,
                on_delivery=on_delivery,
            )

            remaining_messages = self._producer.flush(
                self._delivery_timeout_seconds
            )

        except (KafkaException, BufferError) as exc:

            raise EventPublicationError(
                "Failed to publish thesis event."
            ) from exc

        if remaining_messages > 0:

            raise EventPublicationError(
                "Kafka delivery confirmation timed out."
            )

        if delivery_errors:

            raise EventPublicationError(
                f"Kafka delivery failed: {delivery_errors[0]}"
            )