from dataclasses import dataclass
from uuid import UUID

from identity.application.ports import AccountRepository
from identity.domain.account import Account, Role


@dataclass
class ProvisionAccountUseCase:

    accounts: AccountRepository

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
    ) -> Account:

        account = Account.provision(
            name=name,
            email=email,
            role=role,
            course_id=course_id,
            academic_id=academic_id,
            is_active=is_active,
        )

        return self.accounts.create(account, password)
