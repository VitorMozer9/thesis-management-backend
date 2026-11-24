import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.joinpath("../../..", ".env").resolve())
load_dotenv(Path(__file__).resolve().parent.joinpath("../../..", ".env.repository.local").resolve())
SECRET_KEY = os.environ.get("REPOSITORY_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = os.getenv("REPOSITORY_ALLOWED_HOSTS", "localhost,127.0.0.1,repository-api").split(",")
ROOT_URLCONF = "config.urls"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.postgres", "rest_framework", "repository"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
USE_TZ = True
TIME_ZONE = "UTC"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("REPOSITORY_DB_NAME", "repository_db"),
    "USER": os.getenv("REPOSITORY_DB_USER", "repository_user"),
    "PASSWORD": os.getenv("REPOSITORY_DB_PASSWORD", ""),
    "HOST": os.getenv("REPOSITORY_DB_HOST", "127.0.0.1"),
    "PORT": os.getenv("REPOSITORY_DB_PORT", "5434"),
}}
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["repository.adapters.authentication.AcademicTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
JWT_ISSUER = os.getenv("REPOSITORY_JWT_ISSUER", "")
JWT_AUDIENCE = os.getenv("REPOSITORY_JWT_AUDIENCE", "")
JWT_PUBLIC_KEY_FILE = os.getenv("REPOSITORY_JWT_PUBLIC_KEY_FILE", "")
THESIS_API_URL = os.getenv("REPOSITORY_THESIS_API_URL", "http://127.0.0.1:8001")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("REPOSITORY_KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.getenv("REPOSITORY_KAFKA_TOPIC", "defense.events.v1")
KAFKA_GROUP = os.getenv("REPOSITORY_KAFKA_GROUP", "repository-publication-v1")
MEDIA_ROOT = Path(os.getenv("REPOSITORY_MEDIA_ROOT", Path(__file__).resolve().parents[1] / "media"))
REDIS_URL = os.getenv("REPOSITORY_REDIS_URL", "redis://127.0.0.1:6379/2")
CACHE_TTL = int(os.getenv("REPOSITORY_CACHE_TTL", "120"))
DEFENSE_API_URL = os.getenv("REPOSITORY_DEFENSE_API_URL", "http://127.0.0.1:8003")
VERIFICATION_KEY = os.getenv("REPOSITORY_VERIFICATION_KEY", "")
DATA_UPLOAD_MAX_NUMBER_FILES = 1
FILE_UPLOAD_MAX_MEMORY_SIZE = 256 * 1024
