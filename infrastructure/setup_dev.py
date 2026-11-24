import os
from pathlib import Path
from secrets import token_urlsafe

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


ROOT = Path(__file__).resolve().parents[1]
SECRET_NAMES = (
    "POSTGRES_PASSWORD", "DJANGO_SECRET_KEY", "IDENTITY_SECRET_KEY", "IDENTITY_DB_PASSWORD",
    "DEFENSE_SECRET_KEY", "DEFENSE_DB_PASSWORD", "REPOSITORY_SECRET_KEY", "REPOSITORY_DB_PASSWORD",
    "REPOSITORY_VERIFICATION_KEY", "NOTIFICATION_SECRET_KEY", "NOTIFICATION_DB_PASSWORD",
    "NOTIFICATION_THESIS_KEY", "NOTIFICATION_DEFENSE_KEY", "NOTIFICATION_IDENTITY_KEY",
    "NOTIFICATION_REPOSITORY_KEY",
)


def write_new(path: Path, data: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags, mode), "wb") as output:
        output.write(data)


def main() -> None:
    env_file = ROOT / ".env"
    if env_file.exists():
        raise SystemExit("O .env já existe. Preserve a configuração do ambiente atual.")

    template = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    keys = Path.home() / ".thesis-management" / "keys"
    keys.parent.mkdir(mode=0o700, exist_ok=True)
    keys.mkdir(mode=0o700, exist_ok=True)
    private = keys / "identity-private.pem"
    public = keys / "identity-public.pem"

    if private.exists() != public.exists():
        raise SystemExit("O diretório contém somente uma das chaves RSA. Confira o par existente.")

    if not private.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        write_new(private, key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption(),
        ), 0o600)
        write_new(public, key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ), 0o644)

    values = {name: token_urlsafe(48) for name in SECRET_NAMES}
    values.update(
        IDENTITY_JWT_PRIVATE_KEY_HOST_FILE=f'"{private.as_posix()}"',
        THESIS_JWT_PUBLIC_KEY_HOST_FILE=f'"{public.as_posix()}"',
    )
    configured = []
    for line in template:
        name = line.partition("=")[0]
        configured.append(f"{name}={values[name]}" if name in values else line)

    write_new(env_file, ("\n".join(configured) + "\n").encode(), 0o600)
    print("Configuração local e par RSA disponíveis.")


if __name__ == "__main__":
    main()
