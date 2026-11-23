from dataclasses import dataclass
from uuid import UUID

from identity.application.administration import snapshot
from identity.application.ports import (
    AccountAuditAction,
    AccountAuditEntry,
    AccountAuditPort,
    AccountRepository,
    UnitOfWork,
)
from identity.domain.account import Account, Role


@dataclass
class ProvisionAccountUseCase:

    accounts: AccountRepository
    unit_of_work: UnitOfWork
    audit: AccountAuditPort

    def execute(
        self,
        *,
        name: str,
        email: str,
        role: Role,
        course_id: UUID | None,
        password: str,
        academic_id: UUID | None = None,
        is_active: bool = True,
        provisioned_by: UUID | None = None,
    ) -> Account:

        account = Account.provision(
            name=name,
            email=email,
            role=role,
            course_id=course_id,
            academic_id=academic_id,
            is_active=is_active,
        )

        with self.unit_of_work.transaction():
            created = self.accounts.create(account, password)
            entry = AccountAuditEntry(provisioned_by, created.id, AccountAuditAction.CREATED, snapshot(created))
            self.audit.record(entry)

        return created
