from hmac import compare_digest
from os import getenv

from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET

from defense.adapters.outbound.models import Defense, Member, Outbox


@require_GET
def notification_lookup(request, event_id):
    key = getenv("NOTIFICATION_LOOKUP_KEY", "").encode()
    presented = request.headers.get("Authorization", "").encode()
    if len(key) < 32 or not compare_digest(presented, b"Bearer " + key):
        return HttpResponseForbidden()

    event = Outbox.objects.filter(pk=event_id, event_type__in=("defense.scheduled", "defense.cancelled")).first()
    if event is None:
        raise Http404
    defense = Defense.objects.filter(pk=event.defense_id).first()
    if defense is None:
        raise Http404
    members = Member.objects.filter(defense=defense)
    if event.event_type == "defense.scheduled":
        members = members.filter(invite_status="confirmed")
    else:
        members = members.exclude(invite_status="declined")
    academics = {defense.student_id, defense.advisor_id}
    external = set()
    for member in members:
        if member.academic_id:
            academics.add(member.academic_id)
        else:
            external.add(member.email)
    return JsonResponse({"kind": event.event_type, "aggregate": defense.pk,
                         "academic": sorted(academics), "external": sorted(external)})
