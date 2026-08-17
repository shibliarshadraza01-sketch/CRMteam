"""Final production operations pass: outbound provider integrations.

Each module here (``a1routes``, ``whatsapp``) wraps exactly one external
provider's REST API behind a small client class — credentials are read
from environment variables only (never hardcoded, never returned in any
API response), the same discipline this project already applies to
SendGrid (see ``config/settings/production.py``). Neither provider has
real credentials in this environment; both clients are "provider-ready"
(make real HTTP calls with the real request/response shape each
provider's API documents) but unverified against a live account —
tracked the same way SendGrid was until a real API key exists.
"""
