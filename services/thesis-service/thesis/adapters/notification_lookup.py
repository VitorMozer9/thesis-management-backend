from hmac import compare_digest
from os import getenv

from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET

from thesis.adapters.outbound.persistence.models import ThesisModel
from thesis.adapters.outbound.persistence.outbox_models import OutboxEventModel


@require_GET
def notification_lookup(request, event_id):
    key = getenv("NOTIFICATION_LOOKUP_KEY", "").encode()
    presented = request.headers.get("Authorization", "").encode()
    if len(key) < 32 or not compare_digest(presented, b"Bearer " + key):
        return HttpResponseForbidden()

    event = OutboxEventModel.objects.filter(pk=event_id, event_type="thesis.submitted").first()
    if event is None:
        raise Http404
    thesis = ThesisModel.objects.filter(pk=event.aggregate_id).first()
    if thesis is None:
        raise Http404
    academics = [thesis.advisor_id] if thesis.advisor_id else []
    return JsonResponse({"kind": event.event_type, "aggregate": thesis.pk, "academic": academics, "external": []})


@require_GET
def publication_recipient(request, thesis_id):
    key = getenv("NOTIFICATION_LOOKUP_KEY", "").encode()
    presented = request.headers.get("Authorization", "").encode()
    if len(key) < 32 or not compare_digest(presented, b"Bearer " + key):
        return HttpResponseForbidden()

    student = ThesisModel.objects.filter(pk=thesis_id).values_list("student_id", flat=True).first()
    if student is None:
        raise Http404
    return JsonResponse({"academic": [student], "external": []})
