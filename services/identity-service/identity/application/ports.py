from contextlib import AbstractContextManager
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from identity.domain.account import Account, Role


class AccountAuditAction(StrEnum):
    CREATED = "account.created"
    UPDATED = "account.updated"
    DEACTIVATED = "account.deactivated"
    ACTIVATED = "account.activated"


@dataclass(frozen=True)
class AccountAuditEntry:
    actor_id: UUID | None
    target_id: UUID
    action: AccountAuditAction
    changes: dict[str, Any]


@dataclass(frozen=True)
class AccountFilters:
    role: Role | None = None
    course_id: UUID | None = None
    is_active: bool | None = None
    search: str | None = None


@dataclass(frozen=True)
class AdministrationLock:
    actor: Account | None
    target: Account | None
    active_admin_ids: frozenset[UUID]


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

    def update(self, account: Account) -> Account:
        ...

    def search(self, filters: AccountFilters, offset: int, limit: int) -> list[Account]:
        ...

    def lock_for_administration(self, actor_id: UUID, target_id: UUID | None = None) -> AdministrationLock:
        ...


class UnitOfWork(Protocol):

    def transaction(self) -> AbstractContextManager[None]:
        ...


class AccountAuditPort(Protocol):

    def record(self, entry: AccountAuditEntry) -> None:
        ...


class TokenSigner(Protocol):

    def sign(self, claims: dict[str, Any]) -> str:
        ...
