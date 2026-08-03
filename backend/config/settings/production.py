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
# HTTP with X-Forwarded-Proto; trust it only if the deployment uses a proxy.
# SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
