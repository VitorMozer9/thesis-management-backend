from dataclasses import dataclass
from uuid import UUID

from identity.application.exceptions import InvalidCredentialsError
from identity.application.ports import AccountRepository
from identity.domain.account import Account


@dataclass
class GetProfileUseCase:

    accounts: AccountRepository

    def execute(self, account_id: UUID) -> Account:
        account = self.accounts.find_by_id(account_id)

        if account is None or not account.is_active:
            raise InvalidCredentialsError("Account is unavailable.")

        return account
