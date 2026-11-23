from typing import Any
from uuid import UUID

import jwt

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from identity.application.exceptions import InvalidAccessTokenError


ALGORITHM = "RS256"
TOKEN_TYPE = "at+jwt"
REQUIRED_CLAIMS = ["iss", "aud", "exp", "iat", "sub", "role", "academic_id", "course_id"]


class RsaJwtSigner:

    def __init__(self, private_key: RSAPrivateKey):
        self.private_key = private_key

    def sign(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, self.private_key, algorithm=ALGORITHM, headers={"typ": TOKEN_TYPE})


class RsaJwtVerifier:

    def __init__(self, public_key: RSAPublicKey, issuer: str, audience: str):
        self.public_key = public_key
        self.issuer = issuer
        self.audience = audience

    def verify(self, token: str) -> UUID:
        try:
            verified = jwt.decode_complete(
                token,
                self.public_key,
                algorithms=[ALGORITHM],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": REQUIRED_CLAIMS, "strict_aud": True},
            )

            if verified["header"].get("typ") != TOKEN_TYPE:
                raise ValueError("Expected an access token.")

            return UUID(verified["payload"]["sub"])

        except (jwt.PyJWTError, ValueError, TypeError, AttributeError) as exc:
            raise InvalidAccessTokenError("Invalid access token.") from exc
