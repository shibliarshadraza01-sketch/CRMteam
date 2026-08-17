"""Production settings.

Loaded when DJANGO_SETTINGS_MODULE is explicitly set to this module, or when
DJANGO_ENV is set to "production". Used for deployed/staging environments only.
All security-sensitive values MUST come from environment variables, and the
deployment fails if any required variable is missing (no fallbacks).
"""
from .base import *  # noqa: F401,F403
from .base import env, env_list

# DEBUG is ALWAYS False in production (inherited from base; stated explicitly
# here so a code reviewer sees the production security contract at a glance).
DEBUG = False

# /api/schema/ and /api/docs/ require authentication in production — see
# config/urls.py's own docstring. No third-party integrator consumes this
# API today, so publishing the full endpoint/field surface to the open
# internet is pure reconnaissance value with no offsetting benefit.
API_DOCS_PUBLIC = False

# SECRET_KEY has no fallback in production; the deployment must provide it.
SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "DJANGO_SECRET_KEY environment variable is required in production."
    )

# ALLOWED_HOSTS must be explicitly configured in production; no wildcard.
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ValueError(
        "DJANGO_ALLOWED_HOSTS environment variable is required in production."
    )

# CORS origins must be explicitly configured; no wildcard with credentials.
CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS")
if not CORS_ALLOWED_ORIGINS:
    raise ValueError(
        "DJANGO_CORS_ALLOWED_ORIGINS environment variable is required in production."
    )

# ---------------------------------------------------------------------------
# Security: HTTPS / cookies / headers
# ---------------------------------------------------------------------------
# Enforce HTTPS in production (these are all False by default in Django;
# development.py leaves them off for local http://localhost work).
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Prevent browsers from guessing content type (MIME sniffing).
SECURE_CONTENT_TYPE_NOSNIFF = True

# Enable browser XSS filtering (legacy; modern CSP is better, added later).
SECURE_BROWSER_XSS_FILTER = True

# Enforce HTTPS for one year via Strict-Transport-Security header.
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# The proxy/load-balancer (if any) terminates TLS and forwards to Django over
# HTTP with X-Forwarded-Proto; trust it only if the deployment actually sits
# behind such a proxy (opt-in via env, never assumed) — blindly trusting this
# header without a proxy in front would let a client spoof "I'm HTTPS".
if env("DJANGO_BEHIND_PROXY", "") == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Clickjacking protection (django.middleware.clickjacking.XFrameOptionsMiddleware
# is already installed — see base.py's MIDDLEWARE — DENY is Django's own
# default, stated explicitly here for the same reviewer-visibility reason
# DEBUG is restated above).
X_FRAME_OPTIONS = "DENY"

# Referrer-Policy: never leak the full URL (which can carry query-string
# tokens/IDs) to a cross-origin destination.
SECURE_REFERRER_POLICY = "same-origin"

# CSRF: needed for session-authenticated requests (Django admin login) even
# though the API itself is JWT-authenticated and CSRF-exempt by nature (no
# session cookie is sent). No fallback — an empty list here would make admin
# login on a real domain fail loudly rather than silently accept forgeries.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
if not CSRF_TRUSTED_ORIGINS:
    raise ValueError(
        "DJANGO_CSRF_TRUSTED_ORIGINS environment variable is required in production."
    )

# ---------------------------------------------------------------------------
# Email (SendGrid, via SMTP relay — see base.py's own comment for why no
# SDK dependency is needed)
# ---------------------------------------------------------------------------
SENDGRID_API_KEY = env("DJANGO_SENDGRID_API_KEY")
if not SENDGRID_API_KEY:
    raise ValueError(
        "DJANGO_SENDGRID_API_KEY environment variable is required in production."
    )
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "apikey"  # SendGrid's SMTP relay literally expects this username
EMAIL_HOST_PASSWORD = SENDGRID_API_KEY

# ---------------------------------------------------------------------------
# Cache / distributed rate limiting (final production infrastructure pass)
# ---------------------------------------------------------------------------
# Development's default (Django's in-process LocMemCache) is per-worker —
# fine for a single dev server, but it means throttle counters (login,
# token_refresh, expensive_operation — see base.py's DEFAULT_THROTTLE_RATES)
# are NOT shared across multiple backend instances/workers in production, so
# a rate limit could be bypassed simply by hitting a different process. A
# real Redis instance closes that gap — required here, not optional,
# because this project already runs distributed throttling logic that's
# silently ineffective without a shared cache behind it.
REDIS_URL = env("REDIS_URL")
if not REDIS_URL:
    raise ValueError("REDIS_URL environment variable is required in production (shared cache for distributed rate limiting).")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}
