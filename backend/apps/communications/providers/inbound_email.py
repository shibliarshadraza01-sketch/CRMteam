"""Inbound-email provider verification (customer replies).

Deliberately provider-AGNOSTIC. Every transactional mail provider that
can POST a parsed inbound message to an application (Mailgun, SendGrid
Inbound Parse, Postmark, SES+SNS, a self-hosted LMTP shim) offers the
same two things this module needs:

1. a shared secret we control, and
2. the raw request body.

So verification here is exactly the HMAC-SHA256-over-the-raw-body scheme
``providers/a1routes.py`` already uses for A1 Routes, keyed by
``INBOUND_EMAIL_WEBHOOK_SECRET`` — one signature scheme this project
already has tests, docs and operational habits for, rather than a
second, provider-specific one. A provider whose native scheme differs
(e.g. Mailgun's timestamp+token concatenation) is adapted by a small
shim at the edge (a reverse proxy or a provider-specific subclass of the
webhook view), not by weakening this check.

The secret comes from the environment ONLY and never appears in a
response, a log line, or an error message.
"""
import hashlib
import hmac
import os


class InboundEmailError(Exception):
    """Raised for any inbound-email configuration failure. The message is
    always safe to show an operator (never contains the secret).
    """


def verify_webhook_signature(payload_bytes, signature_header, secret=None):
    """Verify an inbound-email webhook request really came from the
    configured mail provider — HMAC-SHA256 over the raw request body,
    compared in constant time. Returns ``False`` (never raises) for a
    missing/malformed signature or an unconfigured secret; the webhook
    view turns that into a 401 before any database access happens.

    Fail-CLOSED on purpose: with no ``INBOUND_EMAIL_WEBHOOK_SECRET`` set,
    every inbound request is rejected. An unauthenticated endpoint that
    can attach messages to real customer conversations must not be
    reachable just because an environment variable was forgotten.
    """
    secret = secret if secret is not None else os.environ.get("INBOUND_EMAIL_WEBHOOK_SECRET", "")
    if not secret or not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
