from threading import Barrier, Thread
from time import sleep

from django.db import connection
from django.test import TransactionTestCase

from config import dependencies
from identity.adapters.outbound.persistence.audit_models import AccountAuditModel
from identity.adapters.outbound.persistence.django_account_repository import DjangoAccountRepository
from identity.adapters.outbound.persistence.models import User
from identity.application.exceptions import InvalidCredentialsError
from identity.application.ports import AccountAuditAction
from identity.domain.account import Role
from identity.tests.support import IdentitySettingsMixin


LOCK = DjangoAccountRepository.lock_for_administration


def slow_lock(self, actor_id, target_id=None):
    locked = LOCK(self, actor_id, target_id)
    sleep(0.5)

    return locked


class ConcurrentAdministrationTests(IdentitySettingsMixin, TransactionTestCase):

    def run_concurrently(self, *operations):
        barrier = Barrier(len(operations))
        outcomes = [None] * len(operations)

        def run(index, operation):
            try:
                barrier.wait()
                outcomes[index] = operation()

            except Exception as exc:
                outcomes[index] = exc

            finally:
                connection.close()

        threads = [Thread(target=run, args=item) for item in enumerate(operations)]

        DjangoAccountRepository.lock_for_administration = slow_lock

        try:
            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join(timeout=30)

        finally:
            DjangoAccountRepository.lock_for_administration = LOCK

        return outcomes

    def test_administrators_cannot_deactivate_each_other_simultaneously(self):
        first = self.provision(role=Role.ADMIN)
        second = self.provision(role=Role.ADMIN)
        use_case = dependencies.build_set_account_active_use_case

        outcomes = self.run_concurrently(
            lambda: use_case().execute(first.id, second.id, active=False),
            lambda: use_case().execute(second.id, first.id, active=False),
        )

        failures = [outcome for outcome in outcomes if isinstance(outcome, Exception)]

        self.assertEqual(len(failures), 1, outcomes)
        self.assertIsInstance(failures[0], InvalidCredentialsError)
        self.assertEqual(User.objects.filter(role=Role.ADMIN, is_active=True).count(), 1)
        self.assertEqual(AccountAuditModel.objects.filter(action=AccountAuditAction.DEACTIVATED).count(), 1)

    def test_concurrent_updates_are_serialized(self):
        admin = self.provision(role=Role.ADMIN)
        student = self.provision(name="Original")
        use_case = dependencies.build_update_account_use_case

        outcomes = self.run_concurrently(
            lambda: use_case().execute(admin.id, student.id, {"name": "First"}),
            lambda: use_case().execute(admin.id, student.id, {"name": "Second"}),
        )

        self.assertFalse([outcome for outcome in outcomes if isinstance(outcome, Exception)], outcomes)

        changes = [
            record.changes["name"]
            for record in AccountAuditModel.objects.filter(
                target_account_id=student.id, action=AccountAuditAction.UPDATED,
            ).order_by("occurred_at")
        ]

        self.assertEqual(len(changes), 2)
        self.assertEqual(changes[0]["from"], "Original")
        self.assertEqual(changes[1]["from"], changes[0]["to"])
        self.assertEqual(User.objects.get(id=student.id).name, changes[1]["to"])
