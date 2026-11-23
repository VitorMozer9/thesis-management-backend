import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from defense.domain import Missing, Thesis, Unavailable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ThesisClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(NoRedirect())

    def get(self, thesis_id, token):
        request = Request(
            f"{self.base_url}/api/theses/{thesis_id}/",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=5) as response:
                raw = json.loads(response.read(131072))
            thesis = Thesis(UUID(raw["id"]), UUID(raw["course_id"]), UUID(raw["student_id"]),
                            UUID(raw["advisor_id"]) if raw["advisor_id"] else None, raw["status"])
            if thesis.id != thesis_id:
                raise ValueError
            return thesis
        except HTTPError as exc:
            if exc.code in (403, 404):
                raise Missing("Monografia fora do escopo ou inexistente.") from exc
            raise Unavailable("Consulta à monografia indisponível.") from exc
        except (URLError, OSError, ValueError, KeyError, AttributeError, TypeError) as exc:
            raise Unavailable("Consulta à monografia indisponível.") from exc
