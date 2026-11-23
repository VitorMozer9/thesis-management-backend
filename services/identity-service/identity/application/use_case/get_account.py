from dataclasses import dataclass
from uuid import UUID

from identity.application.administration import require_administrator, require_target
from identity.application.ports import AccountRepository
from identity.domain.account import Account


@dataclass
class GetAccountUseCase:

    accounts: AccountRepository

    def execute(self, actor_id: UUID, account_id: UUID) -> Account:
        require_administrator(self.accounts.find_by_id(actor_id))

        return require_target(self.accounts.find_by_id(account_id))
