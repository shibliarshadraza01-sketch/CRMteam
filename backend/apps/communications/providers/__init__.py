"""Final production operations pass: outbound provider integrations.

The module here (``a1routes``) wraps exactly one external provider's REST
API behind a small client class — credentials are read from environment
variables only (never hardcoded, never returned in any API response), the
same discipline this project already applies to SendGrid (see
``config/settings/production.py``). The provider has no real credentials
in this environment; the client is "provider-ready" (makes real HTTP
calls with the real request/response shape the provider's API documents)
but unverified against a live account — tracked the same way SendGrid was
until a real API key exists.

WhatsApp Business API support was removed: it was explicitly descoped by
the project owner (no channel beyond SendGrid email + A1 Routes calling)
and must not be reintroduced.
"""
