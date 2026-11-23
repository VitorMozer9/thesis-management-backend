import json
import logging
from datetime import datetime
from uuid import UUID

from confluent_kafka import Consumer

from thesis.application.use_case.process_submitted_pdf import ProcessSubmittedPdfUseCase
from thesis.domain.events.thesis_events import ThesisSubmittedEvent


logger = logging.getLogger(__name__)


class PdfConsumerError(Exception):
    pass


def parse_event(payload: bytes) -> ThesisSubmittedEvent | None:
    try:
        if not isinstance(payload, bytes) or len(payload) > 65536:
            raise ValueError

        envelope = json.loads(payload)
        event_type = envelope["event_type"]
        if not isinstance(event_type, str) or not event_type:
            raise ValueError
        if event_type != ThesisSubmittedEvent.event_type:
            return None

        if type(envelope["version"]) is not int or envelope["version"] != ThesisSubmittedEvent.version:
            raise ValueError

        thesis_id = UUID(envelope["aggregate_id"])
        occurred_at = datetime.fromisoformat(envelope["occurred_at"])
        if thesis_id != UUID(envelope["data"]["thesis_id"]) or occurred_at.tzinfo is None:
            raise ValueError

        return ThesisSubmittedEvent(
            thesis_id=thesis_id, event_id=UUID(envelope["event_id"]), occurred_at=occurred_at,
        )
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
        raise PdfConsumerError("Envelope inválido ou versão de submissão incompatível.") from None


class PdfEventConsumer:

    def __init__(self, consumer: Consumer, processor: ProcessSubmittedPdfUseCase):
        self.consumer = consumer
        self.processor = processor

    def poll_once(self) -> None:
        message = self.consumer.poll(1.0)
        if message is None:
            return

        location = f"{message.topic()}[{message.partition()}]@{message.offset()}"
        if message.error():
            raise PdfConsumerError(f"Falha na leitura Kafka em {location}.")

        try:
            event = parse_event(message.value())
            if event is not None:
                self.processor.execute(event)

            offsets = self.consumer.commit(message=message, asynchronous=False)
            if any(partition.error for partition in offsets):
                raise PdfConsumerError("Falha na confirmação do offset.")
        except PdfConsumerError as exc:
            raise PdfConsumerError(f"{location}: {exc}") from None
        except Exception as exc:
            raise PdfConsumerError(f"{location}: {type(exc).__name__}. Verifique a infraestrutura e o registro.") from None

        if event is not None:
            logger.info("Evento de PDF confirmado em %s, event_id=%s.", location, event.event_id)
