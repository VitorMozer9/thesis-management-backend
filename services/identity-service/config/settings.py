import os

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent.parent / ".env")


SECRET_KEY = os.environ["IDENTITY_SECRET_KEY"]

DEBUG = os.getenv("IDENTITY_DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("IDENTITY_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]


INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",

    "rest_framework",
    "allauth",
    "allauth.account",
    "identity",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("IDENTITY_DB_NAME", "identity_db"),
        "USER": os.getenv("IDENTITY_DB_USER", "identity_user"),
        "PASSWORD": os.environ["IDENTITY_DB_PASSWORD"],
        "HOST": os.getenv("IDENTITY_DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("IDENTITY_DB_PORT", "5434"),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("IDENTITY_REDIS_URL", "redis://127.0.0.1:6379/1"),
        "KEY_PREFIX": "identity",
    }
}


AUTH_USER_MODEL = "identity.User"

AUTHENTICATION_BACKENDS = [
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


ACCOUNT_ADAPTER = "identity.adapters.outbound.allauth.account_adapter.ClosedSignupAccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_RATE_LIMITS = {
    "login_failed": os.getenv("IDENTITY_LOGIN_FAILED_RATE", "10/m/ip,5/5m/key"),
}


LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "identity.adapters.inbound.rest.authentication.IdentityTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}


IDENTITY_JWT_ISSUER = os.getenv("IDENTITY_JWT_ISSUER", "")
IDENTITY_JWT_AUDIENCE = os.getenv("IDENTITY_JWT_AUDIENCE", "")
IDENTITY_JWT_PRIVATE_KEY = os.getenv("IDENTITY_JWT_PRIVATE_KEY", "").replace("\\n", "\n")

if private_key_file := os.getenv("IDENTITY_JWT_PRIVATE_KEY_FILE"):
    IDENTITY_JWT_PRIVATE_KEY = Path(private_key_file).read_text(encoding="ascii")

IDENTITY_ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("IDENTITY_ACCESS_TOKEN_TTL_SECONDS", "300"))
IDENTITY_MAX_ASSIGNABLE_ADVISORS = int(os.getenv("IDENTITY_MAX_ASSIGNABLE_ADVISORS", "100"))

if not 60 <= IDENTITY_ACCESS_TOKEN_TTL_SECONDS <= 3600:
    raise ImproperlyConfigured("IDENTITY_ACCESS_TOKEN_TTL_SECONDS deve estar entre 60 e 3600.")

if not 1 <= IDENTITY_MAX_ASSIGNABLE_ADVISORS <= 300:
    raise ImproperlyConfigured("IDENTITY_MAX_ASSIGNABLE_ADVISORS deve estar entre 1 e 300.")
