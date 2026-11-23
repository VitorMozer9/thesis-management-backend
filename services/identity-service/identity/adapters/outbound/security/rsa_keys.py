from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey


MIN_RSA_KEY_BITS = 2048


@lru_cache(maxsize=4)
def load_private_key(pem: str) -> RSAPrivateKey:
    try:
        key = serialization.load_pem_private_key(pem.encode("ascii"), password=None)

    except (ValueError, TypeError, UnicodeEncodeError) as exc:
        raise ValueError("Invalid or encrypted RSA private key.") from exc

    if not isinstance(key, RSAPrivateKey) or key.key_size < MIN_RSA_KEY_BITS:
        raise ValueError("Expected an RSA private key of at least 2048 bits.")

    return key


def public_key_pem(key: RSAPrivateKey) -> str:
    return key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
