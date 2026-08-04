"""Base settings shared by all environments.

This module holds configuration that is TRUE EVERYWHERE (installed apps,
middleware, DRF, drf-spectacular, database wiring from environment variables,
etc.). Environment-specific modules (development.py / production.py) import
everything from here with ``from .base import *`` and then override only what
differs for that environment.

Secrets and environment-specific values are read from environment variables,
which are loaded from backend/.env in local development via python-dotenv.
NOTHING secret is hard-coded in this file.
"""
from pathlib import Path

from dotenv import load_dotenv

import os

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# base.py lives at backend/config/settings/base.py, so three .parent hops
# resolve BASE_DIR to the backend/ directory (where manage.py lives).
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from backend/.env if present. In production the
# variables are expected to be provided by the real environment, so a missing
# .env file is not an error.
load_dotenv(BASE_DIR / ".env")


def env(key, default=None):
    """Small helper to read an environment variable with an optional default."""
    return os.environ.get(key, default)


def env_bool(key, default=False):
    """Read a boolean-ish environment variable ("1", "true", "yes")."""
    value = os.environ.get(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(key, default=None):
    """Read a comma-separated environment variable into a list of strings."""
    value = os.environ.get(key)
    if not value:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core security settings
# ---------------------------------------------------------------------------
# SECRET_KEY has NO default on purpose in shared code; each environment module
# is responsible for providing a safe value (dev provides an insecure fallback,
# production requires a real one). See development.py / production.py.
SECRET_KEY = env("DJANGO_SECRET_KEY")

# DEBUG defaults to False here; development.py turns it on.
DEBUG = False

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
]

# Local (project) apps are added here as they are introduced in later
# checkpoints (accounts, leads, customers, ...).
LOCAL_APPS = [
    "apps.accounts",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ---------------------------------------------------------------------------
# Custom user model (CP2)
# ---------------------------------------------------------------------------
# Must be configured BEFORE the project's first `migrate`. Django hard-codes
# the user table's identity into every built-in auth migration the first time
# they run; changing AUTH_USER_MODEL afterward is not a simple settings edit.
# See BACKEND_LEARNING_GUIDE.md CP2 section for the full explanation. This is
# a project-wide identity choice, so it lives in base.py (shared by every
# environment) rather than being duplicated in development.py/production.py.
AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # must precede CommonMiddleware
    "django.middleware.security.SecurityMiddleware",
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
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database (PostgreSQL, configured entirely from environment variables)
# ---------------------------------------------------------------------------
# Real values are supplied via backend/.env (local) or the deployment
# environment (production). No credentials are ever hard-coded here.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST", "localhost"),
        "PORT": env("DB_PORT", "5432"),
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization / time
# ---------------------------------------------------------------------------
# NOTE: The CRM's business timezone lives on the Organization model (introduced
# later) and is used for report/lead-age/date-boundary calculations. This
# Django-level setting keeps stored timestamps in UTC (USE_TZ=True), which is
# the correct foundation for that per-organization logic.
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Primary key type
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    # drf-spectacular introspects views to generate the OpenAPI 3 schema.
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Server-side filtering/search/ordering building blocks (django-filter is
    # the backend used for structured field filtering from CP7 onward).
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    # Default paginate all list endpoints so no view ever returns an unbounded
    # queryset. Individual views can override the page size later.
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    # CP1 ships only public, read-only infrastructure endpoints (health, schema,
    # docs). Real authentication/permission classes are configured in CP3/CP6.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI schema / Swagger docs)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Qualify Learn CRM API",
    "DESCRIPTION": (
        "Backend API for the Qualify Learn CRM. Versioned under /api/v1/. "
        "This checkpoint (CP1) exposes only infrastructure endpoints "
        "(health, schema, docs)."
    ),
    "VERSION": "0.1.0",
    # Don't serve the raw schema from the Swagger UI page itself; the UI fetches
    # it from the dedicated /api/schema/ endpoint.
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# CORS (django-cors-headers)
# ---------------------------------------------------------------------------
# The Next.js frontend runs on a different origin during development, so the
# allowed origins are configured explicitly (never a wildcard alongside
# credentials). Concrete values come from each environment module.
CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS", [])
CORS_ALLOW_CREDENTIALS = True
