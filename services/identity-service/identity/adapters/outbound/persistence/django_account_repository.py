from uuid import UUID

from allauth.account.models import EmailAddress
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from identity.adapters.outbound.persistence.models import User
from identity.domain.account import Account, Role
from identity.domain.exceptions import InvalidAccountError


def to_account(user: User) -> Account:
    return Account(
        id=user.id,
        name=user.name,
        email=user.email,
        role=Role(user.role),
        academic_id=user.academic_id,
        course_id=user.course_id,
        is_active=user.is_active,
    )


class DjangoAccountRepository:

    def find_by_id(self, account_id: UUID) -> Account | None:
        user = User.objects.filter(id=account_id).first()

        return to_account(user) if user else None

    def list_active_advisor_ids(self, course_id: UUID, limit: int) -> list[UUID]:
        advisors = User.objects.filter(role=Role.ADVISOR.value, course_id=course_id, is_active=True)

        return list(advisors.order_by("academic_id").values_list("academic_id", flat=True)[:limit])

    def create(self, account: Account, password: str) -> Account:
        user = User(
            id=account.id,
            name=account.name,
            email=account.email,
            role=account.role.value,
            academic_id=account.academic_id,
            course_id=account.course_id,
            is_active=account.is_active,
        )

        try:
            validate_password(password, user)
            user.set_password(password)
            user.full_clean()

            with transaction.atomic():
                user.save(force_insert=True)
                EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)

        except ValidationError as exc:
            raise InvalidAccountError(" ".join(exc.messages)) from exc

        except IntegrityError as exc:
            raise InvalidAccountError("Email or academic identifier already in use.") from exc

        return to_account(user)
