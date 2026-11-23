from typing import Any
from uuid import UUID

from identity.application.exceptions import (
    AccountNotFoundError,
    AdministrationDeniedError,
    InvalidCredentialsError,
)
from identity.domain.account import Account, Role


AUDITED_FIELDS = ("name", "email", "role", "academic_id", "course_id", "is_active")


def require_administrator(actor: Account | None) -> Account:
    if actor is None or not actor.is_active:
        raise InvalidCredentialsError("Account is unavailable.")

    if actor.role != Role.ADMIN:
        raise AdministrationDeniedError("Account administration requires an active administrator.")

    return actor


def require_target(target: Account | None) -> Account:
    if target is None:
        raise AccountNotFoundError("Account not found.")

    return target


def plain(value: Any) -> Any:
    if isinstance(value, (UUID, Role)):
        return str(value)

    return value


def snapshot(account: Account) -> dict[str, Any]:
    return {field: plain(getattr(account, field)) for field in AUDITED_FIELDS}


def changed_fields(previous: Account, current: Account) -> dict[str, dict[str, Any]]:
    return {
        field: {"from": plain(getattr(previous, field)), "to": plain(getattr(current, field))}
        for field in AUDITED_FIELDS
        if getattr(previous, field) != getattr(current, field)
    }
