from hmac import compare_digest
from os import getenv

from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET

from repository.models import PublicationOutbox


@require_GET
def notification_lookup(request, event_id):
    key = getenv("NOTIFICATION_LOOKUP_KEY", "").encode()
    presented = request.headers.get("Authorization", "").encode()
    if len(key) < 32 or not compare_digest(presented, b"Bearer " + key):
        return HttpResponseForbidden()

    event = PublicationOutbox.objects.filter(pk=event_id).first()
    if event is None:
        raise Http404
    return JsonResponse({"kind": "repository.published", "aggregate": event.thesis_id})
