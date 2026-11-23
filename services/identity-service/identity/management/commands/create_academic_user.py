import sys

from getpass import getpass
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from config import dependencies
from identity.domain.account import Role
from identity.domain.exceptions import InvalidAccountError


class Command(BaseCommand):

    help = "Provisions an academic account. The password is read from stdin or prompted."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)
        parser.add_argument("--role", required=True, choices=[role.value for role in Role])
        parser.add_argument("--course-id", type=UUID)
        parser.add_argument("--academic-id", type=UUID)
        parser.add_argument("--inactive", action="store_true")
        parser.add_argument("--password-stdin", action="store_true")

    def handle(self, *args, **options):
        password = self.read_password(options["password_stdin"])

        try:
            account = dependencies.build_provision_account_use_case().execute(
                name=options["name"],
                email=options["email"],
                role=Role(options["role"]),
                course_id=options["course_id"],
                academic_id=options["academic_id"],
                password=password,
                is_active=not options["inactive"],
            )

        except InvalidAccountError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"account_id={account.id}")
        self.stdout.write(f"academic_id={account.academic_id}")

    def read_password(self, from_stdin: bool) -> str:
        if from_stdin:
            return sys.stdin.readline().rstrip("\r\n")

        password = getpass("Password: ")

        if password != getpass("Password (again): "):
            raise CommandError("Passwords do not match.")

        return password
