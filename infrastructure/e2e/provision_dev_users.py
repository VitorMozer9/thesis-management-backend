import json
import os
import secrets
import uuid

from compose_tools import compose, django_json, users_file


ACCOUNTS = {
    "student": ("student", "Estudante Sintético"),
    "advisor": ("advisor", "Orientador Sintético"),
    "coordinator": ("coordinator", "Coordenação Sintética"),
    "other_student": ("student", "Outro Estudante Sintético"),
    "other_advisor": ("advisor", "Outro Orientador Sintético"),
}


def load_or_create_credentials() -> dict:
    path = users_file()

    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    credentials = {
        "course_id": str(uuid.uuid4()),
        "accounts": {
            key: {
                "email": f"dev-{key.replace('_', '-')}@example.invalid",
                "password": secrets.token_urlsafe(24) + "-Aa1",
            }
            for key in ACCOUNTS
        },
    }

    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "x", encoding="utf-8") as output:
        json.dump(credentials, output, indent=2)

    if os.name != "nt":
        path.chmod(0o600)

    return credentials


def account_exists(email: str) -> dict | None:
    code = (
        "import json; from identity.models import User; "
        f"user = User.objects.filter(email={email!r}).first(); "
        "print(json.dumps(user and {'account_id': str(user.id), 'academic_id': str(user.academic_id), "
        "'role': user.role, 'course_id': str(user.course_id)}))"
    )

    return django_json("identity-api", code)


def provision(key: str, account: dict, course_id: str) -> str:
    role, name = ACCOUNTS[key]

    if account_exists(account["email"]):
        return "existente"

    compose(
        "exec", "-T", "identity-api", "python", "manage.py", "create_academic_user",
        "--email", account["email"], "--name", name, "--role", role,
        "--course-id", course_id, "--password-stdin",
        stdin=account["password"] + "\n",
    )

    return "criada"


def main():
    credentials = load_or_create_credentials()

    for key, account in credentials["accounts"].items():
        outcome = provision(key, account, credentials["course_id"])
        stored = account_exists(account["email"])

        if stored["course_id"] != credentials["course_id"]:
            raise SystemExit(f"{key}: curso divergente no identity-service.")

        print(f"{key}: {outcome} | {account['email']} | role={stored['role']} | academic_id={stored['academic_id']}")

    print(f"course_id={credentials['course_id']}")
    print(f"credenciais privadas: {users_file()}")


if __name__ == "__main__":
    main()
