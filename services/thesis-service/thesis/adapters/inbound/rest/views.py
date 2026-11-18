from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from rest_framework.exceptions import ValidationError

from thesis.domain.exceptions import InvalidThesisError

from thesis.application.use_case.create_thesis import CreateThesisUseCase

from thesis.adapters.outbound.persistence.django_thesis_repository import (
    DjangoThesisRepository,
)

from thesis.adapters.inbound.rest.serializers import ( CreateThesisSerializer,ThesisResponseSerializer,)

from uuid import UUID

from rest_framework.exceptions import NotFound

from thesis.application.use_case.get_thesis import GetThesisUseCase

from thesis.application.use_case.update_thesis import UpdateThesisUseCase

from thesis.application.exceptions import ThesisNotFoundError

from thesis.domain.exceptions import (
    InvalidThesisError,
    ThesisNotEditableError,
)

from thesis.adapters.inbound.rest.exceptions import ConflictError

from thesis.adapters.inbound.rest.serializers import UpdateThesisSerializer

from pathlib import Path
from uuid import UUID

from django.conf import settings

from rest_framework.parsers import MultiPartParser

from thesis.application.use_case.upload_thesis_pdf import (
    UploadThesisPdfUseCase,
)

from thesis.adapters.outbound.storage.local_file_storage import (
    LocalFileStorage,
)

from thesis.adapters.inbound.rest.serializers import (
    UploadThesisPdfSerializer,
)


class ThesisView(APIView):

    def post(self, request):

        serializer = CreateThesisSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        use_case = CreateThesisUseCase(
            repository=DjangoThesisRepository()
        )

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

        use_case = UpdateThesisUseCase(
            repository=DjangoThesisRepository()
        )

        try:
            thesis = use_case.execute(
                thesis_id=thesis_id,
                **serializer.validated_data,
            )

        except ThesisNotFoundError as exc:
            raise NotFound(str(exc)) from exc

        except ThesisNotEditableError as exc:
            raise ConflictError(str(exc)) from exc

        except InvalidThesisError as exc:
            raise ValidationError(
                {"detail": str(exc)}
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

        use_case = UploadThesisPdfUseCase(
            repository=DjangoThesisRepository(),
            storage=LocalFileStorage(
                Path(settings.MEDIA_ROOT)
            ),
        )

        try:
            thesis = use_case.execute(
                thesis_id=thesis_id,
                filename=uploaded_file.name,
                file_size=uploaded_file.size,
                content=uploaded_file,
            )

        except ThesisNotFoundError as exc:
            raise NotFound(str(exc)) from exc

        except ThesisNotEditableError as exc:
            raise ConflictError(str(exc)) from exc

        except InvalidThesisError as exc:
            raise ValidationError(
                {"detail": str(exc)}
            ) from exc

        response_serializer = ThesisResponseSerializer(
            thesis
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )