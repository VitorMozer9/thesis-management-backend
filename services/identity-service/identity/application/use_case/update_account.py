from dataclasses import dataclass
from typing import Any
from uuid import UUID

from identity.application.administration import changed_fields, require_administrator, require_target
from identity.application.exceptions import AdministrationDeniedError
from identity.application.ports import (
    AccountAuditAction,
    AccountAuditEntry,
    AccountAuditPort,
    AccountRepository,
    UnitOfWork,
)
from identity.domain.account import Account, Role


@dataclass
class UpdateAccountUseCase:

    accounts: AccountRepository
    unit_of_work: UnitOfWork
    audit: AccountAuditPort

    def execute(self, actor_id: UUID, account_id: UUID, changes: dict[str, Any]) -> Account:

        with self.unit_of_work.transaction():
            lock = self.accounts.lock_for_administration(actor_id, account_id)
            require_administrator(lock.actor)
            target = require_target(lock.target)

            updated = target.change(**changes)

            if updated.role != target.role and Role.ADMIN in (target.role, updated.role):
                raise AdministrationDeniedError(
                    "Administrator role changes are restricted to trusted provisioning."
                )

            differences = changed_fields(target, updated)

            if not differences:
                return target

            saved = self.accounts.update(updated)
            self.audit.record(AccountAuditEntry(actor_id, target.id, AccountAuditAction.UPDATED, differences))

            return saved
