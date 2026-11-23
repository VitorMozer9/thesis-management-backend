from uuid import UUID

from redis.exceptions import RedisError
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from config import dependencies
from thesis.adapters.inbound.rest.exceptions import ConflictError, ServiceUnavailableError
from thesis.adapters.inbound.rest.serializers import (
    CreateThesisSerializer,
    ListThesesQuerySerializer,
    ThesisResponseSerializer,
    UpdateThesisSerializer,
    UploadThesisPdfSerializer,
)
from thesis.application.exceptions import ThesisAdvisorPermissionError, ThesisNotFoundError
from thesis.application.identity import Role, ThesisAccessDenied
from thesis.application.ports.thesis_lock import ThesisAlreadyLockedError
from thesis.domain.enums.thesis_status import ThesisStatus
from thesis.domain.exceptions import (
    InvalidThesisError,
    InvalidThesisStatusTransitionError,
    ThesisNotEditableError,
    ThesisSubmissionError,
)


class ThesisAPIView(APIView):

    def handle_exception(self, exc):
        if isinstance(exc, ThesisNotFoundError):
            exc = NotFound(str(exc))
        elif isinstance(exc, (ThesisAccessDenied, ThesisAdvisorPermissionError)):
            exc = PermissionDenied(str(exc))
        elif isinstance(exc, (
            ThesisNotEditableError,
            ThesisAlreadyLockedError,
            InvalidThesisStatusTransitionError,
        )):
            exc = ConflictError(str(exc))
        elif isinstance(exc, (InvalidThesisError, ThesisSubmissionError)):
            exc = ValidationError({"detail": str(exc)})
        elif isinstance(exc, RedisError):
            exc = ServiceUnavailableError("Redis is currently unavailable.")

        return super().handle_exception(exc)


class ThesisView(ThesisAPIView):

    def get(self, request):
        query = ListThesesQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        use_case = dependencies.build_list_theses_use_case(request.user)
        theses, has_next = use_case.execute(**query.validated_data)

        return Response({
            "results": ThesisResponseSerializer(theses, many=True).data,
            "has_next": has_next,
        })

    def post(self, request):
        serializer = CreateThesisSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields = serializer.validated_data

        thesis = dependencies.build_create_thesis_use_case(request.user).execute(**fields)
        return Response(ThesisResponseSerializer(thesis).data, status=status.HTTP_201_CREATED)


class ThesisDetailView(ThesisAPIView):

    def get(self, request, thesis_id: UUID):
        thesis = dependencies.build_get_thesis_use_case(request.user).execute(thesis_id)
        return Response(ThesisResponseSerializer(thesis).data)

    def patch(self, request, thesis_id: UUID):
        serializer = UpdateThesisSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        use_case = dependencies.build_update_thesis_use_case(request.user)
        thesis = use_case.execute(thesis_id, **serializer.validated_data)
        return Response(ThesisResponseSerializer(thesis).data)

    def delete(self, request, thesis_id: UUID):
        dependencies.build_delete_thesis_use_case(request.user).execute(thesis_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ThesisPdfUploadView(ThesisAPIView):

    parser_classes = [MultiPartParser]

    def post(self, request, thesis_id: UUID):
        request.user.require_role(Role.STUDENT)
        serializer = UploadThesisPdfSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["file"]

        use_case = dependencies.build_upload_thesis_pdf_use_case(request.user)
        thesis = use_case.execute(
            thesis_id=thesis_id,
            filename=uploaded_file.name,
            file_size=uploaded_file.size,
            content=uploaded_file,
        )
        return Response(ThesisResponseSerializer(thesis).data)


class ThesisUploadStatusView(ThesisAPIView):

    def get(self, request, thesis_id: UUID):
        use_case = dependencies.build_get_thesis_upload_status_use_case(request.user)
        upload_status = use_case.execute(thesis_id)

        return Response({
            "thesis_id": str(thesis_id),
            "upload_status": upload_status.value if upload_status is not None else None,
        })


class ThesisSubmitView(ThesisAPIView):

    def post(self, request, thesis_id: UUID):
        thesis = dependencies.build_submit_thesis_use_case(request.user).execute(thesis_id)
        return Response(ThesisResponseSerializer(thesis).data)


class ThesisReviewView(ThesisAPIView):

    decision: ThesisStatus | None = None

    def post(self, request, thesis_id: UUID):
        request.user.require_role(Role.ADVISOR)
        if request.data:
            raise ValidationError({"detail": "Review requests must have an empty body."})

        use_case = dependencies.build_review_thesis_use_case(request.user)
        thesis = use_case.execute(
            thesis_id,
            authenticated_advisor_id=request.user.academic_id,
            decision=self.decision,
        )
        return Response(ThesisResponseSerializer(thesis).data)
