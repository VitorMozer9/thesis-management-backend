from uuid import uuid4

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from identity.domain.account import MAX_NAME_LENGTH, Role


class UserManager(BaseUserManager):

    use_in_migrations = True

    def create_user(self, email: str, password: str, **fields) -> "User":
        user = self.model(email=email.strip().lower(), **fields)
        user.set_password(password)
        user.save(using=self._db)

        return user


class User(AbstractBaseUser):

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=MAX_NAME_LENGTH)
    email = models.EmailField(max_length=254, unique=True)
    role = models.CharField(max_length=20, choices=[(role.value, role.value) for role in Role])
    academic_id = models.UUIDField(unique=True, default=uuid4, editable=False)
    course_id = models.UUIDField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now, editable=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        db_table = "identity_user"

        constraints = [
            models.UniqueConstraint(Lower("email"), name="identity_user_email_ci_unique"),
            models.CheckConstraint(
                condition=models.Q(role__in=[role.value for role in Role]),
                name="identity_user_role_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(role=Role.ADMIN.value) | models.Q(course_id__isnull=False),
                name="identity_user_course_required",
            ),
        ]

    def __str__(self) -> str:
        return str(self.id)
