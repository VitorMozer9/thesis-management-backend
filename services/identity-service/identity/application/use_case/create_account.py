from dataclasses import dataclass
from uuid import UUID

from identity.application.administration import require_administrator
from identity.application.exceptions import AdministrationDeniedError
from identity.application.ports import AccountRepository, UnitOfWork
from identity.application.use_case.provision_account import ProvisionAccountUseCase
from identity.domain.account import Account, Role


@dataclass
class CreateAccountUseCase:

    accounts: AccountRepository
    unit_of_work: UnitOfWork
    provision: ProvisionAccountUseCase

    def execute(
        self,
        actor_id: UUID,
        *,
        name: str,
        email: str,
        role: Role,
        course_id: UUID | None,
        password: str,
        academic_id: UUID | None = None,
    ) -> Account:

        with self.unit_of_work.transaction():
            require_administrator(self.accounts.lock_for_administration(actor_id).actor)

            if role == Role.ADMIN:
                raise AdministrationDeniedError(
                    "Administrators can only be provisioned with the create_academic_user command."
                )

            return self.provision.execute(
                name=name,
                email=email,
                role=role,
                course_id=course_id,
                password=password,
                academic_id=academic_id,
                provisioned_by=actor_id,
            )
