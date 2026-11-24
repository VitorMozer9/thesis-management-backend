from smtplib import SMTPRecipientsRefused, SMTPResponseException

from django.conf import settings
from django.core.mail import EmailMessage

from notifications.domain import Failure, MESSAGES


class SMTP:
    def send(self, notification, address):
        event = notification.event
        body = f"{MESSAGES[event.kind][1]}\n\nReferência: {event.aggregate_id}\n"
        message = EmailMessage(
            notification.subject, body, settings.DEFAULT_FROM_EMAIL, [address],
            headers={"Message-ID": f"<{notification.id}@{settings.MESSAGE_ID_DOMAIN}>"},
        )
        try:
            if message.send() != 1:
                raise Failure("smtp_unconfirmed")
        except SMTPRecipientsRefused as exc:
            raise Failure("smtp_recipient_refused", permanent=all(code >= 500 for code, _ in exc.recipients.values())) from exc
        except SMTPResponseException as exc:
            raise Failure("smtp_rejected", permanent=exc.smtp_code >= 500) from exc
        except (OSError, ValueError) as exc:
            raise Failure("smtp_unavailable") from exc
