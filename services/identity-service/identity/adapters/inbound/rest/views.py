from rest_framework import status
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied, Throttled
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config import dependencies
from identity.adapters.inbound.rest.serializers import LoginSerializer, ProfileSerializer
from identity.application.exceptions import (
    InvalidCredentialsError,
    TokenServiceUnavailableError,
    TooManyLoginAttemptsError,
)
from identity.domain.exceptions import AccountNotEligibleError


class ServiceUnavailableError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service temporarily unavailable."
    default_code = "service_unavailable"


class IdentityAPIView(APIView):

    def handle_exception(self, exc):
        if isinstance(exc, InvalidCredentialsError):
            exc = AuthenticationFailed("Invalid credentials.")
        elif isinstance(exc, AccountNotEligibleError):
            exc = PermissionDenied(str(exc))
        elif isinstance(exc, TooManyLoginAttemptsError):
            exc = Throttled(detail="Too many failed login attempts.")
        elif isinstance(exc, TokenServiceUnavailableError):
            exc = ServiceUnavailableError("Token service is unavailable.")

        return super().handle_exception(exc)


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

        return Response(ProfileSerializer(account).data, headers={"Cache-Control": "no-store"})
