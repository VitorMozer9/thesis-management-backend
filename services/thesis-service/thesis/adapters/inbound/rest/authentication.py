from functools import lru_cache
from uuid import UUID

import jwt
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from thesis.application.identity import AcademicIdentity, Role


@lru_cache(maxsize=1)
def trusted_key(pem: str) -> RSAPublicKey:
    key = load_pem_public_key(pem.encode("ascii"))
    if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
        raise ValueError("Expected an RSA public key of at least 2048 bits.")

    return key


class AcademicTokenAuthentication(BaseAuthentication):

    def authenticate_header(self, request):
        return "Bearer"

    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts:
            return None

        if len(parts) != 2 or parts[0].lower() != b"bearer" or len(parts[1]) > 16384:
            raise AuthenticationFailed("Invalid bearer credential.")

        trust_settings = (
            settings.THESIS_JWT_PUBLIC_KEY,
            settings.THESIS_JWT_ISSUER,
            settings.THESIS_JWT_AUDIENCE,
        )
        if not all(trust_settings):
            raise AuthenticationFailed("Token verification is unavailable.")

        required = ["iss", "aud", "exp", "iat", "sub", "role", "academic_id", "course_id"]
        try:
            verified = jwt.decode_complete(
                parts[1],
                trusted_key(settings.THESIS_JWT_PUBLIC_KEY),
                algorithms=["RS256"],
                issuer=settings.THESIS_JWT_ISSUER,
                audience=settings.THESIS_JWT_AUDIENCE,
                options={"require": required, "strict_aud": True},
            )
            claims = verified["payload"]
            if verified["header"].get("typ") != "at+jwt":
                raise ValueError("Expected an access token.")

            if any(type(claims[field]) is not int for field in ("iat", "exp")):
                raise ValueError("Invalid token timestamps.")

            advisors = claims.get("assignable_advisor_ids", [])
            if not isinstance(advisors, list):
                raise ValueError("Invalid advisor list.")

            identity = AcademicIdentity(
                account_id=UUID(claims["sub"]),
                role=Role(claims["role"]),
                academic_id=UUID(claims["academic_id"]),
                course_id=UUID(claims["course_id"]),
                assignable_advisors=frozenset(UUID(value) for value in advisors),
            )
        except (
            jwt.PyJWTError,
            ValueError,
            TypeError,
            AttributeError,
            OverflowError,
            UnsupportedAlgorithm,
            RecursionError,
        ) as exc:
            raise AuthenticationFailed("Invalid bearer credential.") from exc

        return identity, None
