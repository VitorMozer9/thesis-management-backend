from dataclasses import dataclass
from uuid import UUID

from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from config import dependencies
from identity.application.exceptions import InvalidAccessTokenError, TokenServiceUnavailableError


MAX_TOKEN_BYTES = 16384


@dataclass(frozen=True)
class TokenPrincipal:
    account_id: UUID

    @property
    def is_authenticated(self) -> bool:
        return True


class IdentityTokenAuthentication(BaseAuthentication):

    def authenticate_header(self, request):
        return "Bearer"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()

        if not parts:
            return None

        if len(parts) != 2 or parts[0].lower() != b"bearer" or len(parts[1]) > MAX_TOKEN_BYTES:
            raise AuthenticationFailed("Invalid bearer credential.")

        try:
            account_id = dependencies.build_token_verifier().verify(parts[1].decode("ascii"))

        except TokenServiceUnavailableError as exc:
            raise AuthenticationFailed("Token verification is unavailable.") from exc

        except (InvalidAccessTokenError, UnicodeDecodeError) as exc:
            raise AuthenticationFailed("Invalid bearer credential.") from exc

        return TokenPrincipal(account_id), None
