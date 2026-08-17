"""WhatsApp Business (Meta Cloud API) provider client.

Credentials come from environment variables only:

- ``WHATSAPP_API_TOKEN`` — permanent/system-user access token.
- ``WHATSAPP_PHONE_ID`` — the sending phone number's Cloud API id.
- ``WHATSAPP_VERIFY_TOKEN`` — the shared secret used during Meta's
  webhook subscription handshake (``GET`` challenge-response) — a
  different value from ``WHATSAPP_API_TOKEN``, never reused for it.
- ``WHATSAPP_APP_SECRET`` — Meta app secret, used to verify the
  ``X-Hub-Signature-256`` header on every inbound webhook POST (Meta's
  own documented verification scheme, HMAC-SHA256 keyed by the app
  secret — the same shape A1 Routes uses, different header name).

None of these ever appear in an API response, log line, or error
message returned to a client.
"""
import hashlib
import hmac
import os

import requests

DEFAULT_API_URL = "https://graph.facebook.com/v19.0"
REQUEST_TIMEOUT_SECONDS = 10


class WhatsAppError(Exception):
    """Raised for any failure calling the WhatsApp Cloud API — network
    error, a non-2xx response, or a malformed response body.
    """


class WhatsAppClient:
    """Thin wrapper around the WhatsApp Cloud API's ``/messages``
    endpoint. One instance per call — cheap to construct, holds no
    long-lived connection state.
    """

    def __init__(self, api_token=None, phone_id=None, api_url=None):
        self.api_token = api_token if api_token is not None else os.environ.get("WHATSAPP_API_TOKEN", "")
        self.phone_id = phone_id if phone_id is not None else os.environ.get("WHATSAPP_PHONE_ID", "")
        self.api_url = (api_url if api_url is not None else os.environ.get("WHATSAPP_API_URL", DEFAULT_API_URL)).rstrip("/")
        if not self.api_token:
            raise WhatsAppError("WHATSAPP_API_TOKEN is not configured.")
        if not self.phone_id:
            raise WhatsAppError("WHATSAPP_PHONE_ID is not configured.")

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}

    def send_message(self, to_number, body):
        """Sends a plain-text WhatsApp message. Returns the provider's
        own message id (a string) on success; raises ``WhatsAppError``
        on any failure. Never logs or returns the API token.
        """
        try:
            response = requests.post(
                f"{self.api_url}/{self.phone_id}/messages",
                json={
                    "messaging_product": "whatsapp",
                    "to": to_number,
                    "type": "text",
                    "text": {"body": body},
                },
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise WhatsAppError(f"Could not reach the WhatsApp Cloud API: {exc}") from exc

        if not response.ok:
            raise WhatsAppError(f"WhatsApp Cloud API rejected the message ({response.status_code}): {response.text[:200]}")

        try:
            data = response.json()
        except ValueError as exc:
            raise WhatsAppError("WhatsApp Cloud API returned a non-JSON response.") from exc

        try:
            message_id = data["messages"][0]["id"]
        except (KeyError, IndexError, TypeError) as exc:
            raise WhatsAppError("WhatsApp Cloud API's response did not include a message id.") from exc
        return message_id


def verify_webhook_signature(payload_bytes, signature_header, app_secret=None):
    """Verifies an inbound WhatsApp webhook request per Meta's own
    documented scheme: ``X-Hub-Signature-256: sha256=<hex hmac>`` over
    the raw request body, HMAC-SHA256 keyed by the app secret. Constant-
    time comparison via ``hmac.compare_digest``. Returns ``False``
    (never raises) for a missing/malformed signature or missing secret.
    """
    app_secret = app_secret if app_secret is not None else os.environ.get("WHATSAPP_APP_SECRET", "")
    if not app_secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    provided = signature_header[len("sha256="):]
    expected = hmac.new(app_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def verify_webhook_subscription_token(token, verify_token=None):
    """Meta's webhook-registration handshake: a ``GET`` request carries
    ``hub.verify_token``, which must match the value configured in the
    Meta App Dashboard (``WHATSAPP_VERIFY_TOKEN``) before this app
    echoes back ``hub.challenge``. A separate, weaker check than the
    HMAC signature above — this one only runs once, at subscription
    setup time, not on every inbound message.
    """
    verify_token = verify_token if verify_token is not None else os.environ.get("WHATSAPP_VERIFY_TOKEN", "")
    return bool(verify_token) and hmac.compare_digest(verify_token, token or "")
