from django.core.management.base import BaseCommand, CommandError

from config import dependencies
from identity.adapters.outbound.security.rsa_keys import public_key_pem
from identity.application.exceptions import TokenServiceUnavailableError


class Command(BaseCommand):

    help = "Prints the PEM public key that other services use to verify access tokens."

    def handle(self, *args, **options):
        try:
            key = dependencies.get_signing_key()

        except TokenServiceUnavailableError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(public_key_pem(key), ending="")
