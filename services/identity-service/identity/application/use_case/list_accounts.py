from dataclasses import dataclass
from uuid import UUID

from identity.application.administration import require_administrator
from identity.application.ports import AccountFilters, AccountRepository
from identity.domain.account import Account


MAX_PAGE_SIZE = 100


@dataclass
class ListAccountsUseCase:

    accounts: AccountRepository

    def execute(
        self,
        actor_id: UUID,
        filters: AccountFilters,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Account], bool]:

        require_administrator(self.accounts.find_by_id(actor_id))

        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
        found = self.accounts.search(filters, (page - 1) * page_size, page_size + 1)

        return found[:page_size], len(found) > page_size
