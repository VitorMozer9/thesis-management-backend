from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from notifications.models import Notification


def visible(actor):
    return Notification.objects.filter(account_id=actor.account_id, academic_id=actor.academic_id).values(
        "id", "event__kind", "subject", "status", "created_at", "sent_at",
    )


class Notifications(APIView):
    def get(self, request):
        return Response({"results": list(visible(request.user).order_by("-created_at", "id")[:100])},
                        headers={"Cache-Control": "no-store"})


class Detail(APIView):
    def get(self, request, notification_id):
        return Response(get_object_or_404(visible(request.user), pk=notification_id),
                        headers={"Cache-Control": "no-store"})
