from uuid import UUID

from redis.exceptions import RedisError

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from rest_framework.exceptions import (
    ValidationError,
    NotFound,
)

from rest_framework.parsers import MultiPartParser

from thesis.domain.exceptions import (
    InvalidThesisError,
    ThesisNotEditableError,
)

from thesis.application.exceptions import ThesisNotFoundError

from thesis.application.ports.thesis_lock import (
    ThesisAlreadyLockedError,
)

from thesis.application.use_case.create_thesis import (
    CreateThesisUseCase,
)

from thesis.application.use_case.get_thesis import (
    GetThesisUseCase,
)

from thesis.adapters.outbound.persistence.django_thesis_repository import (
    DjangoThesisRepository,
)

from thesis.adapters.inbound.rest.exceptions import (
    ConflictError,
    ServiceUnavailableError,
)

from thesis.adapters.inbound.rest.serializers import (
    CreateThesisSerializer,
    ThesisResponseSerializer,
    UpdateThesisSerializer,
    UploadThesisPdfSerializer,
)

from config.dependencies import (
    build_update_thesis_use_case,
    build_upload_thesis_pdf_use_case,
)

from config.dependencies import (
    build_get_thesis_upload_status_use_case,
)

from config.dependencies import (
    build_create_thesis_use_case,
)

class ThesisView(APIView):

    def post(self, request):

        serializer = CreateThesisSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        use_case = build_create_thesis_use_case()

        try:
            thesis = use_case.execute(
                **serializer.validated_data
            )

        except InvalidThesisError as exc:
            raise ValidationError(
                {"detail": str(exc)}
            ) from exc

        response_serializer = ThesisResponseSerializer(
            thesis
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class ThesisDetailView(APIView):

    def get(self, request, thesis_id: UUID):

        use_case = GetThesisUseCase(
            repository=DjangoThesisRepository()
        )

        try:
            thesis = use_case.execute(thesis_id)

        except ThesisNotFoundError as exc:
            raise NotFound(str(exc)) from exc

        serializer = ThesisResponseSerializer(thesis)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, thesis_id: UUID):

        serializer = UpdateThesisSerializer(
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)

        use_case = build_update_thesis_use_case()

        try:
            thesis = use_case.execute(
                thesis_id=thesis_id,
                **serializer.validated_data,
            )

        except ThesisNotFoundError as exc:
            raise NotFound(str(exc)) from exc

        except (
            ThesisNotEditableError,
            ThesisAlreadyLockedError,
        ) as exc:
            raise ConflictError(str(exc)) from exc

        except InvalidThesisError as exc:
            raise ValidationError(
                {"detail": str(exc)}
            ) from exc

        except RedisError as exc:
            raise ServiceUnavailableError(
                "Redis is currently unavailable."
            ) from exc

        response_serializer = ThesisResponseSerializer(
            thesis
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )


class ThesisPdfUploadView(APIView):

    parser_classes = [MultiPartParser]

    def post(self, request, thesis_id: UUID):

        serializer = UploadThesisPdfSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]

        use_case = build_upload_thesis_pdf_use_case()

        try:
            thesis = use_case.execute(
                thesis_id=thesis_id,
                filename=uploaded_file.name,
                file_size=uploaded_file.size,
                content=uploaded_file,
            )

        except ThesisNotFoundError as exc:
            raise NotFound(str(exc)) from exc

        except (
            ThesisNotEditableError,
            ThesisAlreadyLockedError,
        ) as exc:
            raise ConflictError(str(exc)) from exc

        except InvalidThesisError as exc:
            raise ValidationError(
                {"detail": str(exc)}
            ) from exc

        except RedisError as exc:
            raise ServiceUnavailableError(
                "Redis is currently unavailable."
            ) from exc

        response_serializer = ThesisResponseSerializer(
            thesis
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )
    
class ThesisUploadStatusView(APIView):

    def get(self, request, thesis_id: UUID):

        use_case = build_get_thesis_upload_status_use_case()

        try:
            upload_status = use_case.execute(thesis_id)

        except ThesisNotFoundError as exc:
            raise NotFound(str(exc)) from exc

        except RedisError as exc:
            raise ServiceUnavailableError(
                "Redis is currently unavailable."
            ) from exc

        return Response(
            {
                "thesis_id": str(thesis_id),
                "upload_status": (
                    upload_status.value
                    if upload_status is not None
                    else None
                ),
            },
            status=status.HTTP_200_OK,
        )