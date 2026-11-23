from typing import Any, Protocol
from uuid import UUID

from identity.domain.account import Account


class CredentialVerifier(Protocol):

    def verify(self, email: str, password: str) -> Account | None:
        ...


class AccountRepository(Protocol):

    def find_by_id(self, account_id: UUID) -> Account | None:
        ...

    def list_active_advisor_ids(self, course_id: UUID, limit: int) -> list[UUID]:
        ...

    def create(self, account: Account, password: str) -> Account:
        ...


class TokenSigner(Protocol):

    def sign(self, claims: dict[str, Any]) -> str:
        ...
