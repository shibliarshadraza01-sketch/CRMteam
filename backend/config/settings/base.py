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
from datetime import timedelta
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
    # CP3: token_blacklist is SimpleJWT's own app — it owns the
    # OutstandingToken/BlacklistedToken tables that logout (STEP 7) and
    # refresh-token rotation (see SIMPLE_JWT below) write to. It must be in
    # INSTALLED_APPS for its migrations to be picked up by `migrate`.
    "rest_framework_simplejwt.token_blacklist",
]

# Local (project) apps are added here as they are introduced in later
# checkpoints (accounts, leads, customers, ...).
LOCAL_APPS = [
    "apps.accounts",
    "apps.core",
    "apps.organization",
    "apps.crm",
    "apps.sales",
    "apps.catalog",
    "apps.activities",
    "apps.communications",
    "apps.reports",
    "apps.workflows",
    "apps.integrations",
    "apps.system",
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
    # queryset. CP10: a named class (apps.core.pagination.StandardPagination)
    # replaces the bare DRF default so page size (20, overridable up to 100
    # via ?page_size=) is defined in exactly one place — see that module's
    # docstring. This changes CP5's SessionListView's default page size from
    # 25 to 20 too (a deliberate, requested project-wide change, not a
    # regression — SessionListView's own behavior/tests are otherwise
    # unaffected).
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    # CP3: JWTAuthentication is now the project-wide default so any future
    # view can simply declare `permission_classes = [IsAuthenticated]` and
    # get JWT support for free, without repeating authentication_classes on
    # every view. DEFAULT_PERMISSION_CLASSES stays AllowAny (unchanged from
    # CP1/CP2) so existing public endpoints keep working unmodified — CP3's
    # protected endpoint (/api/v1/auth/me/) opts into IsAuthenticated itself.
    # Full RBAC-driven permission classes arrive in CP6.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    # CP4: a scoped rate applied ONLY to the views that opt in via
    # `throttle_scope = "super_admin_verify"` (the Super Admin access-code
    # verify endpoint) — every other endpoint is unaffected. This uses
    # Django's default cache backend (LocMemCache — in-process, per-worker
    # memory) for counting, which is NOT a production-grade brute-force
    # defense: it resets on every process restart and does not share state
    # across multiple worker processes/machines. It exists as a real, if
    # modest, speed bump today, and as the seam a later checkpoint (CP17,
    # deployment hardening) should replace with a shared cache (e.g. Redis)
    # once one exists — see BACKEND_LEARNING_GUIDE.md CP4, "brute-force
    # considerations", for the full discussion. Explicitly NOT a distributed
    # rate limiter, and not claimed to be one.
    "DEFAULT_THROTTLE_RATES": {
        "super_admin_verify": "5/min",
    },
}

# ---------------------------------------------------------------------------
# SimpleJWT (CP3 authentication)
# ---------------------------------------------------------------------------
# SIGNING_KEY intentionally omitted: SimpleJWT defaults it to SECRET_KEY,
# which is already sourced from the environment (see "Core security
# settings" above) and has no hardcoded fallback in production. Reusing
# SECRET_KEY (rather than inventing a second secret to manage) is SimpleJWT's
# documented default and is appropriate for this checkpoint.
SIMPLE_JWT = {
    # Short-lived: an intercepted/leaked access token self-expires quickly.
    # This is the token sent on every authenticated API request, so it's the
    # one most likely to appear in logs, browser memory, or a proxy.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    # Longer-lived: the refresh token is only sent to /api/v1/auth/refresh/,
    # not on every request, so it's a smaller attack surface even though it's
    # longer-lived. A week balances "don't force daily re-login" against
    # "don't keep a stolen refresh token valid forever".
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    # Rotation: every successful refresh issues a brand new refresh token
    # (not just a new access token). Combined with BLACKLIST_AFTER_ROTATION,
    # the *previous* refresh token is immediately blacklisted, so a refresh
    # token can only ever be used once. If a refresh token is ever stolen and
    # used by an attacker, the legitimate client's next refresh attempt with
    # the now-superseded token will fail — a detectable signal of token theft
    # ("refresh token reuse detection").
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # Every issued access/refresh token updates User.last_login, giving CP12
    # (audit) a free, correct "last seen" signal with no extra code.
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# Super Admin secondary-authentication challenge (CP4)
# ---------------------------------------------------------------------------
# Short-lived, signed (django.core.signing — NOT a JWT) token bridging primary
# email/password login and the secondary access-code verify step for
# SUPER_ADMIN. 5 minutes is enough time for a human to read a physical/2FA-app
# access code and type it in, while keeping the window an intercepted
# challenge would be usable in intentionally small. See
# BACKEND_LEARNING_GUIDE.md CP4, "challenge token security", for the full
# rationale and why this is deliberately not a JWT.
SUPER_ADMIN_CHALLENGE_TTL_SECONDS = 300

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
    # CP10: apps.crm.models.Customer.Status and apps.crm.models.Lead.Status
    # are two different TextChoices classes that both happen to back a
    # field named "status" — drf-spectacular's automatic enum-component
    # naming collides on the field name alone and falls back to an
    # unstable, hash-suffixed name (e.g. "Status80cEnum") unless told
    # explicitly which choices class each schema component should be named
    # after. This is not a bug in either model — both fields are correctly
    # named "status" for their own domain — it's purely a schema-naming
    # disambiguation.
    # CP12: apps.sales.models.Quote.Status and apps.sales.models.Invoice
    # .Status collide on the same "status" field name, for the identical
    # reason as the CP10 pair above.
    # CP17: apps.reports.models.ReportExecution.Status and
    # apps.workflows.models.WorkflowExecution.Status have IDENTICAL choice
    # VALUES (PENDING/RUNNING/COMPLETED/FAILED) as well as the same field
    # name — drf-spectacular treats two same-name, same-value enums as one
    # shared schema component, but can't pick a stable name for that shared
    # component without help. A single override (naming the shared
    # component after ReportExecution's own Status) resolves it for BOTH
    # models — WorkflowExecution.status ends up correctly documented as
    # `$ref: ReportExecutionStatusEnum` too, not a naming mismatch. See
    # BACKEND_LEARNING_GUIDE.md CP17 for the fuller explanation of why this
    # differs from the CP10/CP12 pairs above (same name, DIFFERENT values)
    # and from CP16 (no collision at all, since every same-named `status`
    # field that checkpoint added had different values from every other).
    "ENUM_NAME_OVERRIDES": {
        "CustomerStatusEnum": "apps.crm.models.Customer.Status",
        "LeadStatusEnum": "apps.crm.models.Lead.Status",
        "QuoteStatusEnum": "apps.sales.models.Quote.Status",
        "InvoiceStatusEnum": "apps.sales.models.Invoice.Status",
        "ReportExecutionStatusEnum": "apps.reports.models.ReportExecution.Status",
    },
}

# ---------------------------------------------------------------------------
# CORS (django-cors-headers)
# ---------------------------------------------------------------------------
# The Next.js frontend runs on a different origin during development, so the
# allowed origins are configured explicitly (never a wildcard alongside
# credentials). Concrete values come from each environment module.
CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS", [])
CORS_ALLOW_CREDENTIALS = True
