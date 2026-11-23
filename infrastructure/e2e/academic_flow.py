import argparse
import base64
import json
import os
import time
import uuid

from urllib.error import HTTPError
from urllib.request import Request, urlopen

from compose_tools import django_json, users_file


IDENTITY_URL = os.getenv("IDENTITY_URL", "http://127.0.0.1:8002")
THESIS_URL = os.getenv("THESIS_URL", "http://127.0.0.1:8001")
DENIED = {403, 404}


class FlowError(Exception):
    pass


def check(label: str, condition: bool, detail: object = "") -> None:
    if not condition:
        raise FlowError(f"FALHOU: {label} {detail}")

    print(f"ok  {label}")


def call(method: str, url: str, token: str | None = None, body: object = None, raw: bytes | None = None,
         content_type: str = "application/json") -> tuple[int, object]:

    headers = {"Content-Type": content_type}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)

    try:
        with urlopen(Request(url, data=data, method=method, headers=headers), timeout=30) as response:
            payload = response.read()
            return response.status, json.loads(payload) if payload else None

    except HTTPError as error:
        payload = error.read()

        try:
            return error.code, json.loads(payload) if payload else None

        except ValueError:
            return error.code, None


def unverified_claims(token: str) -> dict:
    segment = token.split(".")[1]

    return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))


def text_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode("ascii")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
    ]

    output = bytearray(b"%PDF-1.4\n")
    offsets = []

    for number, item in enumerate(objects, start=1):
        offsets.append(len(output))
        output += b"%d 0 obj\n" % number + item + b"\nendobj\n"

    xref = len(output)
    output += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)

    for offset in offsets:
        output += b"%010d 00000 n \n" % offset

    output += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)

    return bytes(output)


def multipart(filename: str, content: bytes) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()

    return body, f"multipart/form-data; boundary={boundary}"


def wait_for(label: str, probe, timeout: float = 90) -> object:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        result = probe()

        if result:
            return result

        time.sleep(2)

    raise FlowError(f"FALHOU: tempo esgotado aguardando {label}")


class AcademicFlow:

    def __init__(self, credentials: dict):
        self.credentials = credentials
        self.marker = f"Synthetic thesis text {uuid.uuid4().hex[:8]}"

    def login(self, key: str, password: str | None = None) -> tuple[int, object]:
        account = self.credentials["accounts"][key]

        return call(
            "POST",
            f"{IDENTITY_URL}/api/auth/login/",
            body={"email": account["email"], "password": password or account["password"]},
        )

    def token(self, key: str) -> str:
        status, body = self.login(key)
        check(f"login {key} emite JWT", status == 200 and body["token_type"] == "Bearer", status)

        return body["access_token"]

    def outbox(self, thesis_id: str) -> list:
        return django_json("thesis-api", (
            "import json; from thesis.adapters.outbound.persistence.outbox_models import OutboxEventModel as O; "
            f"print(json.dumps([[e.event_type, e.published_at is not None] for e in "
            f"O.objects.filter(aggregate_id='{thesis_id}').order_by('occurred_at')]))"
        ))

    def extraction(self, thesis_id: str) -> dict | None:
        return django_json("thesis-api", (
            "import json; from thesis.models import PdfExtractionModel as P; "
            f"p = P.objects.filter(thesis_id='{thesis_id}').first(); "
            "print(json.dumps(p and {'status': p.status, 'failure_code': p.failure_code, "
            f"'marker': {self.marker!r} in p.text}}))"
        ))

    def audit(self, thesis_id: str) -> list:
        return django_json("thesis-api", (
            "import json; from thesis.models import ThesisAuditModel as A; "
            f"print(json.dumps([[a.action, a.role, str(a.account_id)] for a in "
            f"A.objects.filter(thesis_id='{thesis_id}').order_by('occurred_at')]))"
        ))

    def published(self, thesis_id: str, event_type: str) -> bool:
        return [event_type, True] in self.outbox(thesis_id)

    def run(self) -> str:
        student = self.token("student")
        early_token = student
        status, profile = call("GET", f"{IDENTITY_URL}/api/auth/me/", student)
        check("GET /api/auth/me/ do estudante", status == 200 and profile["role"] == "student", status)

        claims = unverified_claims(student)
        check("JWT RS256 at+jwt com sub distinto de academic_id",
              claims["sub"] != claims["academic_id"] and claims["iss"] == "urn:tcc:identity", claims.get("iss"))

        status, thesis = call("POST", f"{THESIS_URL}/api/theses/", student, {
            "title": "Monografia sintética de integração",
            "abstract": "Resumo sintético para validação ponta a ponta.",
            "student_id": profile["academic_id"],
            "course_id": profile["course_id"],
        })
        check("estudante cria rascunho", status == 201 and thesis["status"] == "draft", (status, thesis))
        thesis_id = thesis["id"]

        status, _ = call("PATCH", f"{THESIS_URL}/api/theses/{thesis_id}/", student, {"keywords": ["integracao"]})
        check("estudante define palavras-chave", status == 200, status)

        coordinator = self.token("coordinator")
        status, advisor_profile = call("GET", f"{IDENTITY_URL}/api/auth/me/", self.token("advisor"))
        advisor_id = advisor_profile["academic_id"]
        check("orientador consta em assignable_advisor_ids",
              advisor_id in unverified_claims(coordinator).get("assignable_advisor_ids", []))

        status, thesis = call("PATCH", f"{THESIS_URL}/api/theses/{thesis_id}/", coordinator, {"advisor_id": advisor_id})
        check("coordenador associa orientador elegível", status == 200 and thesis["advisor_id"] == advisor_id, status)

        body, content_type = multipart("tcc.pdf", text_pdf(self.marker))
        status, thesis = call("POST", f"{THESIS_URL}/api/theses/{thesis_id}/pdf/", student, raw=body,
                              content_type=content_type)
        check("estudante envia PDF textual", status == 200 and thesis["file_sha256"], status)

        status, thesis = call("POST", f"{THESIS_URL}/api/theses/{thesis_id}/submit/", student)
        check("estudante submete", status == 200 and thesis["status"] == "submitted", status)

        wait_for("Outbox thesis.submitted", lambda: self.published(thesis_id, "thesis.submitted"))
        check("Outbox publicou thesis.created e thesis.submitted no Kafka",
              self.published(thesis_id, "thesis.created"))

        extraction = wait_for("extração do PDF", lambda: (
            (result := self.extraction(thesis_id)) and result["status"] in ("completed", "failed") and result
        ))
        check("worker extraiu o texto do PDF via Kafka",
              extraction["status"] == "completed" and extraction["marker"], extraction)

        advisor = self.token("advisor")
        other_advisor = self.token("other_advisor")
        status, _ = call("POST", f"{THESIS_URL}/api/theses/{thesis_id}/approve/", other_advisor)
        check("orientador não vinculado não aprova", status in DENIED, status)

        status, thesis = call("POST", f"{THESIS_URL}/api/theses/{thesis_id}/approve/", advisor)
        check("orientador vinculado aprova", status == 200 and thesis["status"] == "advisor_approved", status)

        wait_for("Outbox thesis.advisor_approved", lambda: self.published(thesis_id, "thesis.advisor_approved"))
        check("Outbox publicou thesis.advisor_approved", True)

        actions = self.audit(thesis_id)
        expected = [
            "thesis.created", "thesis.metadata_updated", "thesis.advisor_assigned",
            "thesis.pdf_uploaded", "thesis.submitted", "thesis.advisor_approved",
        ]
        check("auditoria completa e na ordem", [row[0] for row in actions] == expected, actions)
        check("auditoria registra sub do JWT de cada ator",
              actions[0][2] == claims["sub"] and actions[2][1] == "coordinator" and actions[-1][1] == "advisor")

        self.negative_checks(thesis_id, student)
        self.early_token = early_token

        return thesis_id

    def negative_checks(self, thesis_id: str, student: str) -> None:
        status, _ = call("GET", f"{THESIS_URL}/api/theses/{thesis_id}/")
        check("thesis sem token: 401", status == 401, status)

        status, _ = call("GET", f"{IDENTITY_URL}/api/auth/me/")
        check("identity /me sem token: 401", status == 401, status)

        tampered = student[:-6] + ("AAAAAA" if not student.endswith("AAAAAA") else "BBBBBB")
        status, _ = call("GET", f"{THESIS_URL}/api/theses/{thesis_id}/", tampered)
        check("token adulterado: 401", status == 401, status)

        header, payload, signature = student.split(".")
        claims = unverified_claims(student)
        claims["role"] = "admin"
        forged_payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        status, _ = call("GET", f"{THESIS_URL}/api/theses/{thesis_id}/", f"{header}.{forged_payload}.{signature}")
        check("claims alteradas com assinatura original: 401", status == 401, status)

        status, _ = self.login("student", "Wrong-Password-123")
        check("login com senha incorreta: 401", status == 401, status)

        status, _ = call("POST", f"{IDENTITY_URL}/api/auth/login/", body={
            **{k: v for k, v in self.credentials["accounts"]["student"].items()}, "role": "admin",
        })
        check("login com papel no corpo: 400", status == 400, status)

        status, _ = call("GET", f"{THESIS_URL}/api/theses/{thesis_id}/", self.token("other_student"))
        check("outro estudante não acessa a monografia", status in DENIED, status)

        for path in ("/api/auth/signup/", "/accounts/signup/", "/admin/"):
            status, _ = call("POST", f"{IDENTITY_URL}{path}", body={"email": "x@example.invalid"})
            check(f"identity sem rota pública {path}", status == 404, status)

    def wait_for_expiration(self) -> None:
        expires_at = unverified_claims(self.early_token)["exp"]
        remaining = expires_at - time.time() + 2

        print(f"..  aguardando {max(0, int(remaining))} s pela expiração natural do primeiro token")
        time.sleep(max(0, remaining))

        status, _ = call("GET", f"{THESIS_URL}/api/theses/", self.early_token)
        check("token expirado no thesis-service: 401", status == 401, status)

        status, _ = call("GET", f"{IDENTITY_URL}/api/auth/me/", self.early_token)
        check("token expirado no identity-service: 401", status == 401, status)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-expiration", action="store_true")
    parser.add_argument("--previous-thesis")
    arguments = parser.parse_args()

    flow = AcademicFlow(json.loads(users_file().read_text(encoding="utf-8")))

    if arguments.previous_thesis:
        status, thesis = call("GET", f"{THESIS_URL}/api/theses/{arguments.previous_thesis}/", flow.token("student"))
        check("monografia anterior permanece disponível",
              status == 200 and thesis["status"] == "advisor_approved", (status, thesis))

    thesis_id = flow.run()
    print(f"thesis_id={thesis_id}")

    if not arguments.skip_expiration:
        flow.wait_for_expiration()

    print("RESULTADO: fluxo acadêmico completo aprovado")


if __name__ == "__main__":
    main()
