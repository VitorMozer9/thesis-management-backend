import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.joinpath("../../..", ".env").resolve())
load_dotenv(Path(__file__).resolve().parent.joinpath("../../..", ".env.defense.local").resolve())
SECRET_KEY = os.environ.get("DEFENSE_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = os.getenv("DEFENSE_ALLOWED_HOSTS", "localhost,127.0.0.1,defense-api").split(",")
ROOT_URLCONF = "config.urls"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "rest_framework", "defense"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
USE_TZ = True
TIME_ZONE = "UTC"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("DEFENSE_DB_NAME", "defense_db"),
    "USER": os.getenv("DEFENSE_DB_USER", "defense_user"),
    "PASSWORD": os.getenv("DEFENSE_DB_PASSWORD", ""),
    "HOST": os.getenv("DEFENSE_DB_HOST", "127.0.0.1"),
    "PORT": os.getenv("DEFENSE_DB_PORT", "5434"),
}}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["defense.adapters.inbound.authentication.AcademicTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
JWT_ISSUER = os.getenv("DEFENSE_JWT_ISSUER", "")
JWT_AUDIENCE = os.getenv("DEFENSE_JWT_AUDIENCE", "")
JWT_PUBLIC_KEY_FILE = os.getenv("DEFENSE_JWT_PUBLIC_KEY_FILE", "")
THESIS_API_URL = os.getenv("DEFENSE_THESIS_API_URL", "http://127.0.0.1:8001")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("DEFENSE_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("DEFENSE_KAFKA_TOPIC", "defense.events.v1")
