from django.http import FileResponse, Http404
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.dependencies import service
from repository.adapters.documents import Documents
from repository.domain import Conflict, Forbidden, Unavailable
from .catalog import PUBLIC_FIELDS, cached_search, public_data, public_entries
from .serializers import Document, Metadata, Search


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Dependência indisponível."


class PublicView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]


class Catalog(PublicView):
    def get(self, request):
        query = Search(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(cached_search(query.validated_data))


class Detail(PublicView):
    def get(self, request, thesis_id):
        row = public_entries().filter(pk=thesis_id).values(*PUBLIC_FIELDS).first()
        if row is None:
            raise Http404
        return Response(public_data(row))


class Download(PublicView):
    def get(self, request, thesis_id):
        digest = public_entries().filter(pk=thesis_id).values_list("final_hash", flat=True).first()
        if not digest:
            raise Http404
        try:
            stream = service().documents.verified(thesis_id, digest)
        except OSError as exc:
            raise ServiceUnavailable from exc
        return FileResponse(stream, content_type="application/pdf", as_attachment=True, filename=f"{thesis_id}.pdf")


class Administration(APIView):
    def write(self, request, thesis_id, serializer, field):
        if request.user.role not in ("admin", "coordinator"):
            raise PermissionDenied
        if field == "document":
            try:
                length = int(request.META.get("CONTENT_LENGTH") or 0)
            except ValueError:
                return Response({"detail": "Tamanho de requisição inválido."}, status=400)
            if length > Documents.limit + 65536:
                return Response({"detail": "O PDF deve ter até 20 MiB."}, status=413)
        body = serializer(data=request.data)
        body.is_valid(raise_exception=True)
        try:
            state = service().administer(thesis_id, request.user, request.auth, **{field: body.validated_data})
        except Forbidden as exc:
            raise PermissionDenied from exc
        except (Unavailable, OSError) as exc:
            raise ServiceUnavailable from exc
        except Conflict as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response({"state": state})


class EditMetadata(Administration):
    parser_classes = [JSONParser]

    def put(self, request, thesis_id):
        return self.write(request, thesis_id, Metadata, "metadata")


class RegisterDocument(Administration):
    parser_classes = [MultiPartParser]

    def post(self, request, thesis_id):
        return self.write(request, thesis_id, Document, "document")
