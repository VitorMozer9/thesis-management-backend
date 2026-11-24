from dataclasses import fields
from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from repository.domain import Conflict, Publication
from repository.models import Audit, CatalogRevision, Entry, Receipt


class Records:
    transaction = staticmethod(transaction.atomic)

    def lock(self, thesis_id, course_id):
        entry, _ = Entry.objects.select_for_update().get_or_create(thesis_id=thesis_id, defaults={"course_id": course_id})
        return Publication(**{field.name: getattr(entry, field.name) for field in fields(Publication)})

    def receive(self, event):
        receipt, created = Receipt.objects.get_or_create(event_id=event.event_id, defaults={"fingerprint": event.fingerprint})
        if receipt.fingerprint != event.fingerprint:
            raise Conflict("Identificador de evento reutilizado.")
        return created

    def seen(self, event):
        return Receipt.objects.filter(event_id=event.event_id, fingerprint=event.fingerprint).exists()

    def audit(self, entry, action, actor_id=None, event_id=None):
        Audit.objects.create(thesis_id=entry.thesis_id, action=action, actor_id=actor_id, event_id=event_id)

    def publish(self, entry):
        entry.published_at = timezone.now()
        CatalogRevision.objects.update_or_create(pk=1, defaults={"revision": uuid4()})

    def save(self, entry):
        changes = {field.name: getattr(entry, field.name) for field in fields(entry) if field.name != "thesis_id"}
        Entry.objects.filter(pk=entry.thesis_id).update(**changes)
