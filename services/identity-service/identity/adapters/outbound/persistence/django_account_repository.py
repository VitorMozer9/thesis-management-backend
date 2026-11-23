from uuid import UUID

from allauth.account.models import EmailAddress
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q

from identity.adapters.outbound.persistence.models import User
from identity.application.ports import AccountFilters, AdministrationLock
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

    def update(self, account: Account) -> Account:
        user = User.objects.get(id=account.id)

        user.name = account.name
        user.email = account.email
        user.role = account.role.value
        user.course_id = account.course_id
        user.is_active = account.is_active

        try:
            user.full_clean(exclude=["password"])

            with transaction.atomic():
                user.save(update_fields=["name", "email", "role", "course_id", "is_active"])
                EmailAddress.objects.filter(user=user, primary=True).update(email=user.email)

        except ValidationError as exc:
            raise InvalidAccountError(" ".join(exc.messages)) from exc

        except IntegrityError as exc:
            raise InvalidAccountError("Email already in use.") from exc

        return to_account(user)

    def search(self, filters: AccountFilters, offset: int, limit: int) -> list[Account]:
        users = User.objects.all()

        if filters.role is not None:
            users = users.filter(role=filters.role.value)

        if filters.course_id is not None:
            users = users.filter(course_id=filters.course_id)

        if filters.is_active is not None:
            users = users.filter(is_active=filters.is_active)

        if filters.search:
            users = users.filter(Q(name__icontains=filters.search) | Q(email__icontains=filters.search))

        return [to_account(user) for user in users.order_by("email", "id")[offset:offset + limit]]

    def lock_for_administration(self, actor_id: UUID, target_id: UUID | None = None) -> AdministrationLock:
        ids = [actor_id] if target_id is None else [actor_id, target_id]
        active_admins = Q(role=Role.ADMIN.value, is_active=True)

        locked = {
            user.id: user
            for user in User.objects.select_for_update().filter(active_admins | Q(id__in=ids)).order_by("id")
        }

        return AdministrationLock(
            actor=to_account(locked[actor_id]) if actor_id in locked else None,
            target=to_account(locked[target_id]) if target_id in locked else None,
            active_admin_ids=frozenset(
                user.id for user in locked.values() if user.role == Role.ADMIN.value and user.is_active
            ),
        )
