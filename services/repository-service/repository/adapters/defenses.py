import json
from urllib.error import HTTPError
from urllib.request import Request, build_opener
from uuid import UUID

from repository.adapters.theses import NoRedirect
from repository.domain import Conflict, Unavailable


class DefenseClient:
    def __init__(self, url, key):
        self.url = url.rstrip("/")
        self.key = key

    def verify(self, event):
        if len(self.key) < 32:
            raise Unavailable
        request = Request(f"{self.url}/internal/completed-defenses/{event.defense_id}/",
                          headers={"Authorization": f"Bearer {self.key}"})
        try:
            with build_opener(NoRedirect()).open(request, timeout=5) as response:
                row = json.loads(response.read(8192))
            year = row["defense_year"]
            if (UUID(row["defense_id"]), UUID(row["thesis_id"]), UUID(row["course_id"]), row["result"]) != (
                event.defense_id, event.thesis_id, event.course_id, event.result,
            ) or event.year and event.year != year:
                raise Conflict("Evento incompatível com a banca.")
            if type(year) is not int or not 1900 <= year <= 9999:
                raise Unavailable
            return year
        except HTTPError as exc:
            if exc.code == 404:
                raise Conflict("Banca sem conclusão verificável.") from exc
            raise Unavailable from exc
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise Unavailable from exc
