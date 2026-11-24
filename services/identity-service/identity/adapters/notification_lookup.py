from hmac import compare_digest
from os import getenv

from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET

from identity.adapters.outbound.persistence.models import User


@require_GET
def notification_lookup(request, academic_id):
    key = getenv("NOTIFICATION_LOOKUP_KEY", "").encode()
    presented = request.headers.get("Authorization", "").encode()
    if len(key) < 32 or not compare_digest(presented, b"Bearer " + key):
        return HttpResponseForbidden()

    account = User.objects.filter(academic_id=academic_id, is_active=True).values("id", "email").first()
    if account is None:
        raise Http404
    return JsonResponse(account, headers={"Cache-Control": "no-store"})
