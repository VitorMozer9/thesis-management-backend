from pathlib import Path
from uuid import UUID

import jwt
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from notifications.domain import Actor


class AcademicTokenAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return "Bearer"

    def authenticate(self, request):
        header = get_authorization_header(request).split()
        if not header:
            return None

        try:
            if len(header) != 2 or header[0].lower() != b"bearer" or len(header[1]) > 16384:
                raise ValueError
            if not all((settings.JWT_PUBLIC_KEY_FILE, settings.JWT_ISSUER, settings.JWT_AUDIENCE)):
                raise ValueError
            key = load_pem_public_key(Path(settings.JWT_PUBLIC_KEY_FILE).read_bytes())
            if not isinstance(key, RSAPublicKey) or key.key_size < 2048:
                raise ValueError

            required = ["iss", "aud", "exp", "iat", "sub", "academic_id", "role", "course_id"]
            token = header[1].decode("ascii")
            verified = jwt.decode_complete(
                token, key, algorithms=["RS256"], issuer=settings.JWT_ISSUER,
                audience=settings.JWT_AUDIENCE, options={"require": required, "strict_aud": True},
            )
            claims = verified["payload"]
            if verified["header"].get("typ") != "at+jwt" or claims["role"] not in (
                "student", "advisor", "coordinator", "admin",
            ) or any(type(claims[name]) is not int for name in ("iat", "exp")):
                raise ValueError
            actor = Actor(UUID(claims["sub"]), UUID(claims["academic_id"]), claims["role"], UUID(claims["course_id"]))
        except (jwt.PyJWTError, UnsupportedAlgorithm, OSError, ValueError, TypeError,
                AttributeError, OverflowError, RecursionError) as exc:
            raise AuthenticationFailed("Credencial inválida.") from exc

        return actor, token
