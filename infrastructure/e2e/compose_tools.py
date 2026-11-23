import json
import os
import subprocess

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

COMPOSE_FILES = (
    "infrastructure/compose.yaml",
    "infrastructure/compose.jwt-file.yaml",
    "infrastructure/compose.identity.yaml",
    "infrastructure/compose.identity-key.yaml",
)

DEFAULT_USERS_FILE = Path.home() / ".thesis-management" / "dev-users.json"


def compose_command(*arguments: str) -> list[str]:
    command = ["docker", "compose", "--env-file", ".env"]

    for file in COMPOSE_FILES:
        command += ["-f", file]

    return command + list(arguments)


def compose(*arguments: str, stdin: str | None = None) -> str:
    completed = subprocess.run(
        compose_command(*arguments),
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        env={**os.environ, "MSYS_NO_PATHCONV": "1"},
        timeout=180,
    )

    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())

    return completed.stdout


def django_json(service: str, code: str) -> object:
    output = compose("exec", "-T", service, "python", "manage.py", "shell", "-c", code)

    return json.loads(output.strip().splitlines()[-1])


def users_file() -> Path:
    return Path(os.getenv("THESIS_DEV_USERS_FILE", DEFAULT_USERS_FILE))
