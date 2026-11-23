import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


class ContainerSettingsTests(TestCase):

    def test_external_key_hosts_and_storage(self):
        with TemporaryDirectory() as directory:
            key_path = Path(directory) / "public.pem"
            key_path.write_text("public-test-value", encoding="ascii")
            env = dict(
                os.environ,
                THESIS_JWT_PUBLIC_KEY_FILE=str(key_path),
                THESIS_JWT_PUBLIC_KEY="other-test-value",
                DJANGO_ALLOWED_HOSTS="localhost, thesis-api",
                MEDIA_ROOT=directory,
            )
            subprocess.run(
                [sys.executable, "-c", (
                    "import os; from config import settings; "
                    "assert settings.THESIS_JWT_PUBLIC_KEY == 'public-test-value'; "
                    "assert settings.ALLOWED_HOSTS == ['localhost', 'thesis-api']; "
                    "assert str(settings.MEDIA_ROOT) == os.environ['MEDIA_ROOT']"
                )],
                env=env,
                check=True,
            )
