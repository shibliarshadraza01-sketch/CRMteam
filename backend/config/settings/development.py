"""Development settings.

Loaded by default (manage.py sets DJANGO_SETTINGS_MODULE to this module).
Turns on DEBUG, provides safe local fallbacks, and relaxes host/CORS rules
for local work only. Never used in production.
"""
from .base import *  # noqa: F401,F403
from .base import env, env_list

# Debugging on for local development only.
DEBUG = True

# /api/schema/ and /api/docs/ stay open (no auth) in development for
# usability — see config/urls.py's own docstring. Locked down in
# production (config/settings/production.py).
API_DOCS_PUBLIC = True

# In development we allow an insecure fallback secret key so the project can
# run immediately after checkout even if DJANGO_SECRET_KEY isn't set. This
# fallback is ONLY acceptable because DEBUG-mode dev servers are not exposed.
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1", "0.0.0.0"]
)

# Allow the local Next.js dev server origins by default; override via env.
CORS_ALLOWED_ORIGINS = env_list(
    "DJANGO_CORS_ALLOWED_ORIGINS",
    ["http://localhost:3000", "http://127.0.0.1:3000"],
)

# Emails print to the console instead of actually sending — no SendGrid
# credentials needed for local development. Set DJANGO_SENDGRID_API_KEY to
# route through the real SendGrid relay locally instead (e.g. to manually
# verify delivery against a sandbox inbox).
if env("DJANGO_SENDGRID_API_KEY", ""):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.sendgrid.net"
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = "apikey"  # SendGrid's SMTP relay literally expects this username
    EMAIL_HOST_PASSWORD = env("DJANGO_SENDGRID_API_KEY")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
