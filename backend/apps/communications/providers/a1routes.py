"""A1 Routes SIP provider client.

Credentials come from environment variables only:

- ``A1ROUTES_API_KEY`` — bearer token for the provider's REST API.
- ``A1ROUTES_API_URL`` — base URL (defaults to A1 Routes' documented
  production endpoint; overridable for a sandbox/staging account).
- ``A1ROUTES_WEBHOOK_SECRET`` — HMAC secret used to verify that an
  inbound webhook request genuinely came from A1 Routes (see
  ``verify_webhook_signature()``) — never the same value as the API key.

None of these three ever appear in an API response, a log line, or an
error message returned to a client — ``initiate_call()`` raises
``A1RoutesError`` with the provider's own error text on failure, which
never includes the credential used to make the request.
"""
import hashlib
import hmac
import os

import requests

DEFAULT_API_URL = "https://api.a1routes.com/v1"
REQUEST_TIMEOUT_SECONDS = 10


class A1RoutesError(Exception):
    """Raised for any failure calling A1 Routes — network error, a
    non-2xx response, or a malformed response body. The message is
    always safe to show to an operator (never includes the API key).
    """


class A1RoutesClient:
    """Thin wrapper around A1 Routes' REST API. One instance per call —
    cheap to construct, holds no long-lived connection state.
    """

    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key if api_key is not None else os.environ.get("A1ROUTES_API_KEY", "")
        self.api_url = (api_url if api_url is not None else os.environ.get("A1ROUTES_API_URL", DEFAULT_API_URL)).rstrip("/")
        if not self.api_key:
            raise A1RoutesError("A1ROUTES_API_KEY is not configured.")

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def initiate_call(self, from_number, to_number):
        """Places an outbound call. Returns the provider's own call id
        (a string) on success; raises ``A1RoutesError`` on any failure.
        Never logs or returns the API key.
        """
        try:
            response = requests.post(
                f"{self.api_url}/calls",
                json={"from": from_number, "to": to_number},
                headers=self._headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise A1RoutesError(f"Could not reach A1 Routes: {exc}") from exc

        if not response.ok:
            raise A1RoutesError(f"A1 Routes rejected the call request ({response.status_code}): {response.text[:200]}")

        try:
            data = response.json()
        except ValueError as exc:
            raise A1RoutesError("A1 Routes returned a non-JSON response.") from exc

        call_id = data.get("call_id")
        if not call_id:
            raise A1RoutesError("A1 Routes' response did not include a call_id.")
        return call_id


def verify_webhook_signature(payload_bytes, signature_header, secret=None):
    """Verifies an inbound A1 Routes webhook request actually came from
    A1 Routes — HMAC-SHA256 over the raw request body, compared with
    constant-time equality (``hmac.compare_digest``) so response timing
    can't be used to guess the signature byte-by-byte. Returns ``False``
    (never raises) for a missing/malformed signature or a missing
    secret — the caller (the webhook view) is responsible for turning
    that into a 401.
    """
    secret = secret if secret is not None else os.environ.get("A1ROUTES_WEBHOOK_SECRET", "")
    if not secret or not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
