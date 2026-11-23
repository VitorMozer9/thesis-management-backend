from collections.abc import Callable
from dataclasses import dataclass
from time import time
from typing import Any
from uuid import UUID, uuid4

from identity.application.exceptions import InvalidCredentialsError
from identity.application.ports import AccountRepository, CredentialVerifier, TokenSigner
from identity.domain.account import Account, Role
from identity.domain.exceptions import AccountNotEligibleError


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_in: int


@dataclass
class IssueAccessTokenUseCase:

    credentials: CredentialVerifier
    accounts: AccountRepository
    signer: TokenSigner
    issuer: str
    audience: str
    lifetime_seconds: int
    max_assignable_advisors: int
    clock: Callable[[], float] = time

    def execute(self, email: str, password: str) -> AccessToken:
        account = self.credentials.verify(email, password)

        if account is None:
            raise InvalidCredentialsError("Invalid credentials.")

        claims = self.claims_for(account)

        return AccessToken(self.signer.sign(claims), self.lifetime_seconds)

    def claims_for(self, account: Account) -> dict[str, Any]:
        course_id = account.token_course()
        issued_at = int(self.clock())

        claims: dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": str(account.id),
            "academic_id": str(account.academic_id),
            "role": account.role.value,
            "course_id": str(course_id),
            "iat": issued_at,
            "exp": issued_at + self.lifetime_seconds,
            "jti": str(uuid4()),
        }

        if account.role == Role.COORDINATOR:
            claims["assignable_advisor_ids"] = [str(value) for value in self.assignable_advisors(course_id)]

        return claims

    def assignable_advisors(self, course_id: UUID) -> list[UUID]:
        advisors = self.accounts.list_active_advisor_ids(course_id, self.max_assignable_advisors + 1)

        if len(advisors) > self.max_assignable_advisors:
            raise AccountNotEligibleError("Too many eligible advisors for a single access token.")

        return advisors
