from dataclasses import dataclass, replace
from uuid import UUID

from identity.application.administration import changed_fields, require_administrator, require_target
from identity.application.exceptions import AdministrationConflictError, AdministrationDeniedError
from identity.application.ports import (
    AccountAuditAction,
    AccountAuditEntry,
    AccountAuditPort,
    AccountRepository,
    AdministrationLock,
    UnitOfWork,
)
from identity.domain.account import Account, Role


@dataclass
class SetAccountActiveUseCase:

    accounts: AccountRepository
    unit_of_work: UnitOfWork
    audit: AccountAuditPort

    def execute(self, actor_id: UUID, account_id: UUID, active: bool) -> Account:

        with self.unit_of_work.transaction():
            lock = self.accounts.lock_for_administration(actor_id, account_id)
            actor = require_administrator(lock.actor)
            target = require_target(lock.target)

            if target.is_active == active:
                return target

            if not active:
                self.ensure_can_deactivate(actor, target, lock)

            updated = replace(target, is_active=active)
            saved = self.accounts.update(updated)

            action = AccountAuditAction.ACTIVATED if active else AccountAuditAction.DEACTIVATED
            self.audit.record(AccountAuditEntry(actor_id, target.id, action, changed_fields(target, updated)))

            return saved

    def ensure_can_deactivate(self, actor: Account, target: Account, lock: AdministrationLock) -> None:
        if target.id == actor.id:
            raise AdministrationDeniedError("Administrators cannot deactivate their own account.")

        if target.role == Role.ADMIN and not lock.active_admin_ids - {target.id}:
            raise AdministrationConflictError("The last active administrator cannot be deactivated.")
