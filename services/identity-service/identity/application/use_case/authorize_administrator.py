from dataclasses import dataclass
from uuid import UUID

from identity.application.administration import require_administrator
from identity.application.ports import AccountRepository
from identity.domain.account import Account


@dataclass
class AuthorizeAdministratorUseCase:

    accounts: AccountRepository

    def execute(self, actor_id: UUID) -> Account:
        return require_administrator(self.accounts.find_by_id(actor_id))
