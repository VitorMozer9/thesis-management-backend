from hmac import compare_digest

from django.conf import settings
from django.http import Http404
from rest_framework.authentication import get_authorization_header
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from config.dependencies import build_service
from defense.domain import Missing, Status


class RepositoryPermission(BasePermission):
    def has_permission(self, request, view):
        key = settings.REPOSITORY_VERIFICATION_KEY.encode()
        return len(key) >= 32 and compare_digest(get_authorization_header(request), b"Bearer " + key)


class CompletedDefense(APIView):
    authentication_classes = []
    permission_classes = [RepositoryPermission]

    def get(self, request, defense_id):
        try:
            defense = build_service().repo.get(defense_id)
        except Missing as exc:
            raise Http404 from exc
        if defense.status != Status.HELD or not defense.result:
            raise Http404
        return Response({"defense_id": defense.id, "thesis_id": defense.thesis_id, "course_id": defense.course_id,
                         "result": defense.result, "defense_year": defense.starts_at.year},
                        headers={"Cache-Control": "no-store"})
