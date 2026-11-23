from contextlib import AbstractContextManager

from django.db import transaction

from thesis.application.ports.unit_of_work import (
    UnitOfWorkPort,
)


class DjangoUnitOfWork(UnitOfWorkPort):

    def transaction(
        self,
    ) -> AbstractContextManager[None]:

        return transaction.atomic()