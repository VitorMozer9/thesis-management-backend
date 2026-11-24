import json
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from notifications.domain import Failure


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Contacts:
    def __init__(self, endpoints):
        self.endpoints = endpoints
        self.opener = build_opener(NoRedirect())

    def get(self, source, path):
        base, key = self.endpoints[source]
        if len(key) < 32:
            raise Failure("lookup_configuration", permanent=True)

        request = Request(f"{base.rstrip('/')}/internal/notification-{path}/",
                          headers={"Authorization": f"Bearer {key}"})
        try:
            with self.opener.open(request, timeout=4) as response:
                data = json.loads(response.read(262144))
            if not isinstance(data, dict):
                raise ValueError
            return data
        except HTTPError as exc:
            if exc.code == 404:
                raise Failure("source_not_found") from exc
            if exc.code in (401, 403):
                raise Failure("lookup_authorization", permanent=True) from exc
            raise Failure("lookup_unavailable") from exc
        except (OSError, ValueError, RecursionError) as exc:
            raise Failure("lookup_unavailable") from exc

    def recipients(self, event):
        source = event.kind.split(".")[0]
        data = self.get(source, f"events/{event.id}")
        try:
            if data["kind"] != event.kind or UUID(data["aggregate"]) != event.aggregate_id:
                raise Failure("event_source_mismatch", permanent=True)
            if source == "repository":
                data = self.get("thesis", f"publications/{event.aggregate_id}")
            if not isinstance(data["academic"], list) or not isinstance(data["external"], list):
                raise ValueError
            academic = {UUID(value) for value in data["academic"]}
            external = {self.email(value) for value in data["external"]}
        except (ValueError, TypeError, AttributeError, KeyError, ValidationError) as exc:
            raise Failure("invalid_recipient_data", permanent=True) from exc

        return academic, external

    def account(self, academic_id):
        data = self.get("identity", f"contacts/{academic_id}")
        try:
            return UUID(data["id"]), self.email(data["email"])
        except (ValueError, TypeError, AttributeError, KeyError, ValidationError) as exc:
            raise Failure("invalid_contact", permanent=True) from exc

    @staticmethod
    def email(value):
        if not isinstance(value, str) or len(value) > 254:
            raise ValueError
        validate_email(value)
        return value.lower()
