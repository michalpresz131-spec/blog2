"""Settings for the AllManiac Django blog."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", True)
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY when DJANGO_DEBUG is false.")
    SECRET_KEY = get_random_secret_key()

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")
    if host.strip()
]
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "blog.apps.BlogConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

turso_url = os.environ.get("TURSO_DATABASE_URL", "").strip()
turso_token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
if bool(turso_url) != bool(turso_token):
    raise ImproperlyConfigured(
        "Set both TURSO_DATABASE_URL and TURSO_AUTH_TOKEN, or leave both empty to use local SQLite."
    )

if turso_url and turso_token:
    parsed_turso_url = urlsplit(turso_url)
    if (
        parsed_turso_url.scheme not in {"https", "libsql", "turso"}
        or not parsed_turso_url.netloc
        or parsed_turso_url.query
        or parsed_turso_url.fragment
    ):
        raise ImproperlyConfigured(
            "TURSO_DATABASE_URL must be a plain https://, libsql://, or turso:// URL without query parameters."
        )
    DATABASES = {
        "default": {
            "ENGINE": "config.db.backends.turso",
            "NAME": turso_url,
            "OPTIONS": {"auth_token": turso_token},
        }
    }
elif not DEBUG:
    raise ImproperlyConfigured(
        "Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN before running with DJANGO_DEBUG=false."
    )
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / os.environ.get("MEDIA_ROOT", "media")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
if os.environ.get("MEDIA_STORAGE_BACKEND", "local").strip().lower() == "s3":
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ.get("AWS_STORAGE_BUCKET_NAME", ""),
            "region_name": os.environ.get("AWS_S3_REGION_NAME") or None,
            "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL") or None,
            "default_acl": None,
            "file_overwrite": False,
        },
    }
elif os.environ.get("MEDIA_STORAGE_BACKEND", "local").strip().lower() != "local":
    raise ImproperlyConfigured("MEDIA_STORAGE_BACKEND must be either 'local' or 's3'.")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/admin/login/"

EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    (
        "django.core.mail.backends.smtp.EmailBackend"
        if os.environ.get("GMAIL_USER") and os.environ.get("GMAIL_APP_PASSWORD")
        else "django.core.mail.backends.console.EmailBackend"
    ),
)
gmail_user = os.environ.get("GMAIL_USER", "")
gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD", "")
if bool(gmail_user) != bool(gmail_app_password):
    raise ImproperlyConfigured("Set both GMAIL_USER and GMAIL_APP_PASSWORD to enable Gmail notifications.")
EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "smtp.gmail.com" if gmail_user else "")
EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", gmail_user)
EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", gmail_app_password)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL", gmail_user or "AllManiac blog <noreply@example.com>"
)
MODERATION_NOTIFICATION_EMAILS = [
    address.strip()
    for address in os.environ.get(
        "MODERATION_NOTIFICATION_EMAILS", os.environ.get("NOTIFY_EMAIL", "")
    ).split(",")
    if address.strip()
]

SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
