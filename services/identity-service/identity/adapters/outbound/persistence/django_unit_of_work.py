from contextlib import AbstractContextManager

from django.db import transaction


class DjangoUnitOfWork:

    def transaction(self) -> AbstractContextManager[None]:
        return transaction.atomic()
