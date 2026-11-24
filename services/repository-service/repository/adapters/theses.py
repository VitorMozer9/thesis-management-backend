import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from repository.domain import Forbidden, Unavailable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ThesisClient:
    def __init__(self, url):
        self.url = url.rstrip("/")

    def verify(self, thesis_id, actor, token):
        request = Request(f"{self.url}/api/theses/{thesis_id}/", headers={"Authorization": f"Bearer {token}"})
        try:
            with build_opener(NoRedirect()).open(request, timeout=5) as response:
                row = json.loads(response.read(131072))
            if UUID(row["id"]) != thesis_id or UUID(row["course_id"]) != actor.course_id:
                raise Forbidden
            if row["status"] not in ("advisor_approved", "defense_approved", "published"):
                return None
            digest = row["file_sha256"]
            if not isinstance(digest, str) or not re.fullmatch("[a-f0-9]{64}", digest):
                raise Unavailable
            return digest
        except HTTPError as exc:
            if exc.code in (401, 403, 404):
                raise Forbidden from exc
            raise Unavailable from exc
        except (URLError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise Unavailable from exc
