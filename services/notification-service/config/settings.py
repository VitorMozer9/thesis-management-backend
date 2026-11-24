import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.joinpath("../../..", ".env").resolve())
load_dotenv(Path(__file__).resolve().parent.joinpath("../../..", ".env.notification.local").resolve())
SECRET_KEY = os.environ.get("NOTIFICATION_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = os.getenv("NOTIFICATION_ALLOWED_HOSTS", "localhost,127.0.0.1,notification-api").split(",")
ROOT_URLCONF = "config.urls"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "rest_framework", "notifications"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
USE_TZ = True
TIME_ZONE = "UTC"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("NOTIFICATION_DB_NAME", "notification_db"),
    "USER": os.getenv("NOTIFICATION_DB_USER", "notification_user"),
    "PASSWORD": os.getenv("NOTIFICATION_DB_PASSWORD", ""),
    "HOST": os.getenv("NOTIFICATION_DB_HOST", "127.0.0.1"),
    "PORT": os.getenv("NOTIFICATION_DB_PORT", "5434"),
}}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["notifications.adapters.authentication.AcademicTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
JWT_ISSUER = os.getenv("NOTIFICATION_JWT_ISSUER", "")
JWT_AUDIENCE = os.getenv("NOTIFICATION_JWT_AUDIENCE", "")
JWT_PUBLIC_KEY_FILE = os.getenv("NOTIFICATION_JWT_PUBLIC_KEY_FILE", "")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("NOTIFICATION_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_GROUP = os.getenv("NOTIFICATION_KAFKA_GROUP", "notification-delivery-v1")
KAFKA_OFFSET_RESET = os.getenv("NOTIFICATION_KAFKA_OFFSET_RESET", "latest")
TOPICS = {
    "thesis": os.getenv("KAFKA_THESIS_EVENTS_TOPIC", "thesis.events.v1"),
    "defense": os.getenv("DEFENSE_KAFKA_TOPIC", "defense.events.v1"),
    "repository": os.getenv("REPOSITORY_PUBLICATION_TOPIC", "repository.events.v1"),
}
LOOKUP_ENDPOINTS = {
    name: (os.getenv(f"NOTIFICATION_{name.upper()}_URL", f"http://127.0.0.1:{port}"),
           os.getenv(f"NOTIFICATION_{name.upper()}_KEY", ""))
    for name, port in (("thesis", 8001), ("identity", 8002), ("defense", 8003), ("repository", 8004))
}
MAX_ATTEMPTS = max(1, int(os.getenv("NOTIFICATION_MAX_ATTEMPTS", "8")))
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("NOTIFICATION_SMTP_HOST", "localhost")
EMAIL_PORT = int(os.getenv("NOTIFICATION_SMTP_PORT", "1025"))
EMAIL_HOST_USER = os.getenv("NOTIFICATION_SMTP_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("NOTIFICATION_SMTP_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("NOTIFICATION_SMTP_TLS", "false").lower() == "true"
EMAIL_TIMEOUT = int(os.getenv("NOTIFICATION_SMTP_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.getenv("NOTIFICATION_FROM_EMAIL", "notificacoes@example.invalid")
MESSAGE_ID_DOMAIN = DEFAULT_FROM_EMAIL.rsplit("@", 1)[-1]
