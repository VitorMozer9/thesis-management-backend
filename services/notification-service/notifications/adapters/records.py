from contextlib import contextmanager

from django.db import transaction

from notifications.models import IncomingEvent, Notification


class Records:
    @contextmanager
    def claim(self, queue, now):
        model = IncomingEvent if queue == "events" else Notification
        with transaction.atomic():
            yield (model.objects.select_for_update(skip_locked=True)
                   .filter(status="pending", next_attempt__lte=now).order_by("next_attempt", "pk").first())

    def enqueue(self, event, academic, external, subject):
        Notification.objects.bulk_create([
            Notification(event=event, recipient=str(value), academic_id=value, subject=subject)
            for value in academic
        ] + [
            Notification(event=event, recipient=value, subject=subject) for value in external
        ])

    def save(self, job):
        job.save()
