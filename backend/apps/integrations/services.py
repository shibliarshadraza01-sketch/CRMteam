"""CP18: API key and webhook services.

API keys reuse Django's OWN password-hashing infrastructure
(`django.contrib.auth.hashers.make_password()`/`check_password()`) —
the SAME machinery CP4's `User.set_access_code()`/`check_access_code()`
already established for the Super Admin secondary access code. No new
hashing scheme is introduced.

Webhook signing uses HMAC-SHA256 over the raw request body, in the
`sha256=<hex>` header format GitHub/Stripe both use, verified with
`hmac.compare_digest()` (constant-time — never a plain `==` comparison of
a signature, which would leak timing information about how many
characters matched).

Ownership scoping is NOT reimplemented — CP10's `managed_user_ids()`/
`scope_queryset_for_user()` are imported directly from `apps.crm.services`.
"""
import hashlib
import hmac
import json
import secrets
import urllib.request
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from apps.crm.services import managed_user_ids, scope_queryset_for_user  # noqa: F401 (re-exported)

from .models import APIKey, Integration, WebhookDelivery, WebhookEndpoint

# --------------------------------------------------------------------------
# Integration
# --------------------------------------------------------------------------


def create_integration(name, *, owner=None, description=""):
    """Create an `Integration`. A thin wrapper — kept as a service function
    for the same single-seam reasoning as CP9's `create_lead()`.
    """
    return Integration.objects.create(name=name, owner=owner, description=description)


# --------------------------------------------------------------------------
# API keys
# --------------------------------------------------------------------------

_API_KEY_PREFIX = "clk_"  # "CRM Live Key" — mirrors Stripe's own sk_live_/pk_live_ convention.


def _generate_raw_key():
    return f"{_API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def generate_api_key(integration, name, *, expires_at=None):
    """Create a new `APIKey` and return `(api_key, raw_key)`.

    `raw_key` is the ONLY time the plaintext secret is ever available —
    the caller (an API endpoint, in practice) must show it to the user
    NOW; it cannot be recovered later, only rotated into a new value
    (`rotate_api_key()`) or revoked (`revoke_api_key()`). Only `key_hash`
    (via `make_password()`) is persisted.
    """
    raw_key = _generate_raw_key()
    api_key = APIKey.objects.create(
        integration=integration,
        name=name,
        key_prefix=raw_key[: len(_API_KEY_PREFIX) + 8],
        key_hash=make_password(raw_key),
        expires_at=expires_at,
    )
    return api_key, raw_key


def rotate_api_key(api_key):
    """Replace `api_key`'s secret with a freshly-generated one, returning
    `(api_key, raw_key)` — same "shown once" contract as
    `generate_api_key()`. The OLD raw key stops working immediately (its
    hash is overwritten, not kept alongside the new one) — this is a
    rotation of the same key's secret, not the creation of a second key.
    Raises `ValueError` if `api_key` is already revoked — rotating a
    revoked key's secret would silently make it usable again, which is
    never the intent of "revoke."
    """
    if api_key.is_revoked:
        raise ValueError("Cannot rotate a revoked API key.")

    raw_key = _generate_raw_key()
    api_key.key_prefix = raw_key[: len(_API_KEY_PREFIX) + 8]
    api_key.key_hash = make_password(raw_key)
    api_key.save(update_fields=["key_prefix", "key_hash", "updated_at"])
    return api_key, raw_key


def revoke_api_key(api_key):
    """Permanently disable `api_key`. Raises `ValueError` if already
    revoked — the same "already closed" guard shape as CP11's
    `mark_won()`/CP14's `complete_task()`.
    """
    if api_key.is_revoked:
        raise ValueError("This API key is already revoked.")

    api_key.revoked_at = timezone.now()
    api_key.is_active = False
    api_key.save(update_fields=["revoked_at", "is_active", "updated_at"])
    return api_key


def verify_api_key(raw_key):
    """Verify a raw API key presented by a caller. Returns the matching
    `APIKey` on success, or `None` — NEVER raises, for anything from "not
    a key-shaped string" through "hash mismatch" through "expired" — a
    bad credential is a normal, expected outcome for this function to
    report, not an error condition. Updates `last_used_at` on success.
    """
    if not raw_key or not raw_key.startswith(_API_KEY_PREFIX):
        return None

    prefix = raw_key[: len(_API_KEY_PREFIX) + 8]
    try:
        api_key = APIKey.active_objects.get(key_prefix=prefix)
    except APIKey.DoesNotExist:
        return None

    if not check_password(raw_key, api_key.key_hash):
        return None
    if api_key.is_expired:
        return None

    api_key.last_used_at = timezone.now()
    api_key.save(update_fields=["last_used_at"])
    return api_key


# --------------------------------------------------------------------------
# Webhook endpoints + signing
# --------------------------------------------------------------------------


def create_webhook_endpoint(integration, url, *, event_types=None):
    """Create a `WebhookEndpoint` with a freshly-generated signing secret."""
    return WebhookEndpoint.objects.create(
        integration=integration, url=url, secret=secrets.token_urlsafe(32), event_types=event_types or []
    )


def regenerate_webhook_secret(endpoint):
    """Replace `endpoint`'s signing secret. Unlike an API key, this is
    NOT a "shown once" secret — see `models.py`'s `WebhookEndpoint`
    docstring for why a webhook secret stays visible to its owner.
    """
    endpoint.secret = secrets.token_urlsafe(32)
    endpoint.save(update_fields=["secret", "updated_at"])
    return endpoint


def sign_payload(secret, payload_bytes):
    """Return the `sha256=<hex>` HMAC signature GitHub/Stripe both use for
    their own outbound webhook signing headers.
    """
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def verify_webhook_signature(secret, payload_bytes, signature):
    """Verify a `sign_payload()` signature using a CONSTANT-TIME
    comparison (`hmac.compare_digest()`) — a plain `==` here would leak,
    via response-time differences, how many leading characters of a
    forged signature matched the real one, letting an attacker recover
    the correct signature one byte at a time. This is the receiving
    side's counterpart to `sign_payload()`; this project's own webhook
    SENDER doesn't call it (we only need to sign our own outbound
    payloads), but any future webhook RECEIVER this project builds
    should verify inbound signatures with this exact function, not a
    hand-rolled comparison.
    """
    expected = sign_payload(secret, payload_bytes)
    return hmac.compare_digest(expected, signature)


# --------------------------------------------------------------------------
# Webhook delivery + retry scheduling
# --------------------------------------------------------------------------

#: Exponential backoff, capped — the Nth retry waits min(2**N, 60) minutes.
#: A deliberately simple schedule, not a configurable/pluggable backoff
#: strategy — "basic X only," the same scope discipline CP14's
#: `generate_occurrences()`/CP15's `render_template()` both applied.
_MAX_RETRY_DELAY_MINUTES = 60


def schedule_retry(delivery):
    """Compute and store WHEN `delivery` should next be attempted — pure
    date-math, not an actual re-attempt. "Retry scheduling" in this
    checkpoint means deciding a `next_retry_at` timestamp for
    `WebhookDelivery.objects.due_for_retry()` to later find; there is no
    background worker in this project that automatically acts on it (the
    same "abstraction, not a real scheduler" honesty as CP15's
    `queue_email()`/`send_queued_email()` split).
    """
    delay_minutes = min(2**delivery.attempt_count, _MAX_RETRY_DELAY_MINUTES)
    delivery.next_retry_at = timezone.now() + timedelta(minutes=delay_minutes)
    delivery.save(update_fields=["next_retry_at", "updated_at"])
    return delivery


def _default_send_func(url, payload_bytes, signature):
    """The real (non-test) delivery path — a plain stdlib
    `urllib.request` POST (no new third-party HTTP client dependency for
    a single outbound call). Raises on any non-2xx response or network
    error; `deliver_webhook()` catches it.
    """
    request = urllib.request.Request(
        url,
        data=payload_bytes,
        method="POST",
        headers={"Content-Type": "application/json", "X-Webhook-Signature": signature},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status


def deliver_webhook(endpoint, event_type, payload, *, send_func=None):
    """Attempt delivery of one event to `endpoint`. Creates a
    `WebhookDelivery`, signs `payload` with `endpoint.secret`, and calls
    `send_func` (defaulting to `_default_send_func`, injectable for
    testing — the same dependency-injection shape CP15's
    `send_queued_email()` established for its own external-service
    boundary). NEVER lets an exception propagate: success marks
    DELIVERED with `delivered_at`/`response_status_code` set; failure
    marks FAILED, increments `attempt_count`, records `error_message`,
    and calls `schedule_retry()` — the same "a failure is a recorded
    fact, not a crash" contract every prior checkpoint's external-service
    boundary (CP15's email, CP16's report computation, CP17's workflow
    actions) has established.
    """
    send_func = send_func or _default_send_func

    delivery = WebhookDelivery.objects.create(
        endpoint=endpoint, event_type=event_type, payload=payload, status=WebhookDelivery.Status.PENDING
    )
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = sign_payload(endpoint.secret, payload_bytes)

    delivery.attempt_count += 1
    try:
        status_code = send_func(endpoint.url, payload_bytes, signature)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any delivery failure is "FAILED", not a crash
        delivery.status = WebhookDelivery.Status.FAILED
        delivery.error_message = str(exc)
        delivery.save(update_fields=["status", "error_message", "attempt_count", "updated_at"])
        schedule_retry(delivery)
        return delivery

    delivery.status = WebhookDelivery.Status.DELIVERED
    delivery.response_status_code = status_code
    delivery.delivered_at = timezone.now()
    delivery.save(update_fields=["status", "response_status_code", "delivered_at", "attempt_count", "updated_at"])
    return delivery


__all__ = [
    "managed_user_ids",
    "scope_queryset_for_user",
    "create_integration",
    "generate_api_key",
    "rotate_api_key",
    "revoke_api_key",
    "verify_api_key",
    "create_webhook_endpoint",
    "regenerate_webhook_secret",
    "sign_payload",
    "verify_webhook_signature",
    "schedule_retry",
    "deliver_webhook",
]
