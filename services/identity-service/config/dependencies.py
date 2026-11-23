from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from django.conf import settings
from django.http import HttpRequest

from identity.adapters.outbound.allauth.credentials import AllauthCredentialVerifier
from identity.adapters.outbound.persistence.django_account_audit import DjangoAccountAudit
from identity.adapters.outbound.persistence.django_account_repository import DjangoAccountRepository
from identity.adapters.outbound.persistence.django_unit_of_work import DjangoUnitOfWork
from identity.adapters.outbound.security.jwt_tokens import RsaJwtSigner, RsaJwtVerifier
from identity.adapters.outbound.security.rsa_keys import load_private_key
from identity.application.exceptions import TokenServiceUnavailableError
from identity.application.use_case.authorize_administrator import AuthorizeAdministratorUseCase
from identity.application.use_case.create_account import CreateAccountUseCase
from identity.application.use_case.get_account import GetAccountUseCase
from identity.application.use_case.get_profile import GetProfileUseCase
from identity.application.use_case.issue_access_token import IssueAccessTokenUseCase
from identity.application.use_case.list_accounts import ListAccountsUseCase
from identity.application.use_case.provision_account import ProvisionAccountUseCase
from identity.application.use_case.set_account_active import SetAccountActiveUseCase
from identity.application.use_case.update_account import UpdateAccountUseCase


def get_signing_key() -> RSAPrivateKey:
    configured = (
        settings.IDENTITY_JWT_PRIVATE_KEY,
        settings.IDENTITY_JWT_ISSUER,
        settings.IDENTITY_JWT_AUDIENCE,
    )

    if not all(configured):
        raise TokenServiceUnavailableError("Token signing is not configured.")

    try:
        return load_private_key(settings.IDENTITY_JWT_PRIVATE_KEY)

    except ValueError as exc:
        raise TokenServiceUnavailableError("Token signing key is invalid.") from exc


def build_issue_access_token_use_case(request: HttpRequest) -> IssueAccessTokenUseCase:

    return IssueAccessTokenUseCase(
        credentials=AllauthCredentialVerifier(request),
        accounts=DjangoAccountRepository(),
        signer=RsaJwtSigner(get_signing_key()),
        issuer=settings.IDENTITY_JWT_ISSUER,
        audience=settings.IDENTITY_JWT_AUDIENCE,
        lifetime_seconds=settings.IDENTITY_ACCESS_TOKEN_TTL_SECONDS,
        max_assignable_advisors=settings.IDENTITY_MAX_ASSIGNABLE_ADVISORS,
    )


def build_token_verifier() -> RsaJwtVerifier:

    return RsaJwtVerifier(
        public_key=get_signing_key().public_key(),
        issuer=settings.IDENTITY_JWT_ISSUER,
        audience=settings.IDENTITY_JWT_AUDIENCE,
    )


def build_get_profile_use_case() -> GetProfileUseCase:
    return GetProfileUseCase(accounts=DjangoAccountRepository())


def build_provision_account_use_case() -> ProvisionAccountUseCase:

    return ProvisionAccountUseCase(
        accounts=DjangoAccountRepository(),
        unit_of_work=DjangoUnitOfWork(),
        audit=DjangoAccountAudit(),
    )


def build_authorize_administrator_use_case() -> AuthorizeAdministratorUseCase:
    return AuthorizeAdministratorUseCase(accounts=DjangoAccountRepository())


def build_create_account_use_case() -> CreateAccountUseCase:

    return CreateAccountUseCase(
        accounts=DjangoAccountRepository(),
        unit_of_work=DjangoUnitOfWork(),
        provision=build_provision_account_use_case(),
    )


def build_get_account_use_case() -> GetAccountUseCase:
    return GetAccountUseCase(accounts=DjangoAccountRepository())


def build_list_accounts_use_case() -> ListAccountsUseCase:
    return ListAccountsUseCase(accounts=DjangoAccountRepository())


def build_update_account_use_case() -> UpdateAccountUseCase:

    return UpdateAccountUseCase(
        accounts=DjangoAccountRepository(),
        unit_of_work=DjangoUnitOfWork(),
        audit=DjangoAccountAudit(),
    )


def build_set_account_active_use_case() -> SetAccountActiveUseCase:

    return SetAccountActiveUseCase(
        accounts=DjangoAccountRepository(),
        unit_of_work=DjangoUnitOfWork(),
        audit=DjangoAccountAudit(),
    )
