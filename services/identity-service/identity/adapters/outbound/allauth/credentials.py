from allauth.account.adapter import get_adapter
from django.core.exceptions import ValidationError
from django.http import HttpRequest

from identity.adapters.outbound.persistence.django_account_repository import to_account
from identity.application.exceptions import TooManyLoginAttemptsError
from identity.domain.account import Account


class AllauthCredentialVerifier:

    def __init__(self, request: HttpRequest):
        self.request = request

    def verify(self, email: str, password: str) -> Account | None:
        try:
            user = get_adapter(self.request).authenticate(self.request, email=email, password=password)

        except ValidationError as exc:
            raise TooManyLoginAttemptsError("Too many failed login attempts.") from exc

        if user is None or not user.is_active:
            return None

        return to_account(user)
