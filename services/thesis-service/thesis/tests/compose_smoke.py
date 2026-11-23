import hashlib
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, urlopen
from uuid import uuid4

import django
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa



def call(path, method, token, data=None, content_type="application/json"):
    if data is not None and not isinstance(data, bytes):
        data = json.dumps(data).encode()

    request = Request(
        "http://127.0.0.1:8091/api/theses/" + path,
        method=method,
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": content_type},
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main():
    from thesis.models import PdfExtractionModel
    from thesis.tests.test_pdf_worker import make_pdf

    issuer = "urn:test:" + str(uuid4())
    audience = "urn:test:thesis"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    course, student, advisor = (str(uuid4()) for _ in range(3))

    def sign(role, academic_id, **grants):
        now = int(time.time())
        return jwt.encode({
            "iss": issuer, "aud": audience, "sub": str(uuid4()), "role": role,
            "academic_id": academic_id, "course_id": course, "iat": now, "exp": now + 300, **grants,
        }, key, algorithm="RS256", headers={"typ": "at+jwt"})

    with TemporaryDirectory() as directory:
        pem = Path(directory) / "public.pem"
        pem.write_bytes(key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
        ))
        env = dict(os.environ, THESIS_JWT_PUBLIC_KEY_FILE=str(pem), THESIS_JWT_ISSUER=issuer,
                   THESIS_JWT_AUDIENCE=audience)
        server = subprocess.Popen(
            ["gunicorn", "--bind", "127.0.0.1:8091", "config.wsgi:application"], env=env
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError("Gunicorn encerrou antes do teste.")
                try:
                    with socket.create_connection(("127.0.0.1", 8091), timeout=1):
                        break
                except OSError:
                    time.sleep(0.1)

            owner = sign("student", student)
            created = call("", "POST", owner, {
                "title": "Teste Docker", "abstract": "Documento sintético",
                "student_id": student, "course_id": course,
            })
            thesis_id = created["id"]
            print("Monografia sintética:", thesis_id, flush=True)
            detail = thesis_id + "/"
            call(detail, "PATCH", owner, {"keywords": ["docker"]})
            coordinator = sign("coordinator", str(uuid4()), assignable_advisor_ids=[advisor])
            call(detail, "PATCH", coordinator, {"advisor_id": advisor})

            pdf = make_pdf("Docker PDF smoke test")
            boundary = uuid4().hex
            header = f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="sample.pdf"\r\n'
            body = header.encode() + b"Content-Type: application/pdf\r\n\r\n" + pdf
            body += f"\r\n--{boundary}--\r\n".encode()
            call(detail + "pdf/", "POST", owner, body, f"multipart/form-data; boundary={boundary}")
            call(detail + "submit/", "POST", owner)

            for _ in range(90):
                result = PdfExtractionModel.objects.get(thesis_id=thesis_id)
                if result.status == "completed":
                    if result.text != "Docker PDF smoke test" or result.file_sha256 != hashlib.sha256(pdf).hexdigest():
                        raise RuntimeError("Resultado extraído divergente.")
                    print("Submissão autenticada e extração verificadas.")
                    return
                if result.status == "failed":
                    raise RuntimeError(result.failure_code)
                time.sleep(1)
            raise RuntimeError("Tempo de espera da extração esgotado.")
        finally:
            server.terminate()
            server.wait(timeout=35)


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()
    main()
