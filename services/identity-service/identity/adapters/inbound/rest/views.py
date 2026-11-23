from uuid import UUID

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config import dependencies
from identity.adapters.inbound.rest.permissions import IsActiveAdministrator
from identity.adapters.inbound.rest.serializers import (
    AccountCreateSerializer,
    AccountQuerySerializer,
    AccountUpdateSerializer,
    LoginSerializer,
    ProfileSerializer,
)
from identity.application.exceptions import (
    AccountNotFoundError,
    AdministrationConflictError,
    AdministrationDeniedError,
    InvalidCredentialsError,
    TokenServiceUnavailableError,
    TooManyLoginAttemptsError,
)
from identity.application.ports import AccountFilters
from identity.domain.account import Role
from identity.domain.exceptions import AccountNotEligibleError, InvalidAccountError


NO_STORE = {"Cache-Control": "no-store"}


class ServiceUnavailableError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service temporarily unavailable."
    default_code = "service_unavailable"


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state."
    default_code = "conflict"


class IdentityAPIView(APIView):

    def handle_exception(self, exc):
        if isinstance(exc, InvalidCredentialsError):
            exc = AuthenticationFailed("Invalid credentials.")
        elif isinstance(exc, (AccountNotEligibleError, AdministrationDeniedError)):
            exc = PermissionDenied(str(exc))
        elif isinstance(exc, AccountNotFoundError):
            exc = NotFound(str(exc))
        elif isinstance(exc, AdministrationConflictError):
            exc = ConflictError(str(exc))
        elif isinstance(exc, InvalidAccountError):
            exc = ValidationError({"detail": str(exc)})
        elif isinstance(exc, TooManyLoginAttemptsError):
            exc = Throttled(detail="Too many failed login attempts.")
        elif isinstance(exc, TokenServiceUnavailableError):
            exc = ServiceUnavailableError("Token service is unavailable.")

        return super().handle_exception(exc)


class AdministrationView(IdentityAPIView):

    permission_classes = [IsAuthenticated, IsActiveAdministrator]


class LoginView(IdentityAPIView):

    authentication_classes = []
    permission_classes = [AllowAny]

    def get_authenticate_header(self, request):
        return "Bearer"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = dependencies.build_issue_access_token_use_case(request._request)
        token = use_case.execute(**serializer.validated_data)

        body = {"access_token": token.value, "token_type": "Bearer", "expires_in": token.expires_in}

        return Response(body, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


class ProfileView(IdentityAPIView):

    def get(self, request):
        account = dependencies.build_get_profile_use_case().execute(request.user.account_id)

        return Response(ProfileSerializer(account).data, headers=NO_STORE)


class UserCollectionView(AdministrationView):

    def get(self, request):
        query = AccountQuerySerializer(data=request.query_params.dict())
        query.is_valid(raise_exception=True)
        params = query.validated_data

        filters = AccountFilters(
            role=Role(params["role"]) if "role" in params else None,
            course_id=params.get("course_id"),
            is_active=params["is_active"],
            search=params.get("search"),
        )

        use_case = dependencies.build_list_accounts_use_case()
        accounts, has_next = use_case.execute(request.user.account_id, filters, params["page"], params["page_size"])

        body = {
            "results": ProfileSerializer(accounts, many=True).data,
            "page": params["page"],
            "page_size": params["page_size"],
            "has_next": has_next,
        }

        return Response(body, headers=NO_STORE)

    def post(self, request):
        serializer = AccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fields = {**serializer.validated_data, "role": Role(serializer.validated_data["role"])}

        account = dependencies.build_create_account_use_case().execute(request.user.account_id, **fields)

        headers = {**NO_STORE, "Location": f"/api/users/{account.id}/"}

        return Response(ProfileSerializer(account).data, status=status.HTTP_201_CREATED, headers=headers)


class UserDetailView(AdministrationView):

    def get(self, request, account_id: UUID):
        account = dependencies.build_get_account_use_case().execute(request.user.account_id, account_id)

        return Response(ProfileSerializer(account).data, headers=NO_STORE)

    def patch(self, request, account_id: UUID):
        serializer = AccountUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)

        if "role" in changes:
            changes["role"] = Role(changes["role"])

        use_case = dependencies.build_update_account_use_case()
        account = use_case.execute(request.user.account_id, account_id, changes)

        return Response(ProfileSerializer(account).data, headers=NO_STORE)


class UserActivationView(AdministrationView):

    active: bool = True

    def post(self, request, account_id: UUID):
        if request.data:
            raise ValidationError({"detail": "Activation requests must have an empty body."})

        use_case = dependencies.build_set_account_active_use_case()
        account = use_case.execute(request.user.account_id, account_id, self.active)

        return Response(ProfileSerializer(account).data, headers=NO_STORE)
