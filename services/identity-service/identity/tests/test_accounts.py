from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from allauth.account.models import EmailAddress
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import RequestFactory

from identity.adapters.outbound.allauth.account_adapter import ClosedSignupAccountAdapter
from identity.adapters.outbound.persistence.models import User
from identity.domain.account import Account, Role
from identity.domain.exceptions import InvalidAccountError
from identity.tests.support import TEST_PASSWORD, IdentityTestCase


class AccountProvisioningTests(IdentityTestCase):

    def test_password_is_stored_as_salted_hash(self):
        account = self.provision()
        user = User.objects.get(id=account.id)

        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertNotIn(TEST_PASSWORD, user.password)
        self.assertTrue(user.check_password(TEST_PASSWORD))
        self.assertNotEqual(user.password, User.objects.get(id=self.provision().id).password)

    def test_academic_id_is_independent_from_account_id(self):
        account = self.provision()

        self.assertNotEqual(account.id, account.academic_id)
        self.assertEqual(User.objects.get(id=account.id).academic_id, account.academic_id)

    def test_email_is_normalized_unique_and_verified(self):
        account = self.provision(email="  Ana.Souza@Example.EDU ")

        self.assertEqual(account.email, "ana.souza@example.edu")
        self.assertTrue(EmailAddress.objects.filter(user_id=account.id, verified=True, primary=True).exists())

        with self.assertRaises(InvalidAccountError):
            self.provision(email="ANA.SOUZA@example.edu")

        self.assertEqual(User.objects.count(), 1)

    def test_weak_password_is_rejected_without_creating_account(self):
        for password in ("short", "12345678901234", "password12345"):
            with self.subTest(password=password), self.assertRaises(InvalidAccountError):
                self.provision(password=password)

        self.assertFalse(User.objects.exists())

    def test_course_is_required_except_for_admin(self):
        with self.assertRaises(InvalidAccountError):
            self.provision(role=Role.STUDENT, course_id=None)

        admin = self.provision(role=Role.ADMIN, course_id=None)

        self.assertIsNone(admin.course_id)

    def test_database_enforces_course_and_role_constraints(self):
        for fields in ({"role": "student", "course_id": None}, {"role": "root", "course_id": uuid4()}):
            with self.subTest(fields=fields), self.assertRaises(IntegrityError), transaction.atomic():
                User.objects.create_user(email=f"{uuid4().hex}@example.edu", password=TEST_PASSWORD, name="X", **fields)

    def test_invalid_role_and_name_are_rejected(self):
        with self.assertRaises(InvalidAccountError):
            Account.provision(name="Ana", email="a@example.edu", role="root", course_id=uuid4())

        with self.assertRaises(InvalidAccountError):
            Account.provision(name="  ", email="a@example.edu", role=Role.STUDENT, course_id=uuid4())

    def test_public_signup_is_closed(self):
        request = RequestFactory().get("/")

        self.assertFalse(ClosedSignupAccountAdapter().is_open_for_signup(request))

        for path in ("/accounts/signup/", "/accounts/login/", "/admin/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


class CreateAcademicUserCommandTests(IdentityTestCase):

    def run_command(self, *args, password=TEST_PASSWORD):
        output = StringIO()

        with patch("sys.stdin", StringIO(password + "\n")):
            call_command("create_academic_user", *args, "--password-stdin", stdout=output)

        return output.getvalue()

    def test_creates_account_from_trusted_cli_input(self):
        output = self.run_command(
            "--email", "prof@example.edu", "--name", "Prof. Lima",
            "--role", "advisor", "--course-id", str(self.course_id),
        )
        user = User.objects.get(email="prof@example.edu")

        self.assertIn(f"account_id={user.id}", output)
        self.assertIn(f"academic_id={user.academic_id}", output)
        self.assertNotIn(TEST_PASSWORD, output)
        self.assertEqual(user.role, Role.ADVISOR)

    def test_reports_validation_errors(self):
        with self.assertRaises(CommandError):
            self.run_command(
                "--email", "x@example.edu", "--name", "X", "--role", "student",
                "--course-id", str(self.course_id), password="123",
            )
