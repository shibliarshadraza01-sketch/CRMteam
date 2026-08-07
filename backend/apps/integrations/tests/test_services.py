"""CP18: tests for apps/integrations/services.py."""
import pytest

from apps.integrations.models import APIKey, WebhookDelivery
from apps.integrations.services import (
    _generate_raw_key,
    create_integration,
    create_webhook_endpoint,
    deliver_webhook,
    generate_api_key,
    managed_user_ids,
    regenerate_webhook_secret,
    revoke_api_key,
    rotate_api_key,
    schedule_retry,
    scope_queryset_for_user,
    sign_payload,
    verify_api_key,
    verify_webhook_signature,
)

# --------------------------------------------------------------------------
# No database required — pure crypto/date-math
# --------------------------------------------------------------------------


def test_managed_user_ids_and_scope_queryset_for_user_are_reexported_from_crm():
    from apps.crm import services as crm_services

    assert managed_user_ids is crm_services.managed_user_ids
    assert scope_queryset_for_user is crm_services.scope_queryset_for_user


def test_generate_raw_key_has_expected_prefix_and_is_unpredictable():
    first = _generate_raw_key()
    second = _generate_raw_key()
    assert first.startswith("clk_")
    assert second.startswith("clk_")
    assert first != second


def test_sign_payload_is_deterministic_for_same_secret_and_body():
    sig1 = sign_payload("secret", b'{"a":1}')
    sig2 = sign_payload("secret", b'{"a":1}')
    assert sig1 == sig2
    assert sig1.startswith("sha256=")


def test_sign_payload_differs_for_different_secrets():
    sig1 = sign_payload("secret-a", b'{"a":1}')
    sig2 = sign_payload("secret-b", b'{"a":1}')
    assert sig1 != sig2


def test_verify_webhook_signature_accepts_correct_signature():
    sig = sign_payload("secret", b'{"a":1}')
    assert verify_webhook_signature("secret", b'{"a":1}', sig) is True


def test_verify_webhook_signature_rejects_tampered_payload():
    sig = sign_payload("secret", b'{"a":1}')
    assert verify_webhook_signature("secret", b'{"a":2}', sig) is False


def test_verify_webhook_signature_rejects_wrong_secret():
    sig = sign_payload("secret", b'{"a":1}')
    assert verify_webhook_signature("wrong-secret", b'{"a":1}', sig) is False


def test_verify_api_key_rejects_none_and_empty():
    assert verify_api_key(None) is None
    assert verify_api_key("") is None


def test_verify_api_key_rejects_wrong_prefix_without_hitting_db():
    assert verify_api_key("not_a_clk_key") is None


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_integration_basic(employee):
    integration = create_integration("Zapier", owner=employee)
    assert integration.owner_id == employee.id


@pytest.mark.django_db
def test_generate_api_key_returns_raw_key_and_never_stores_it(integration):
    api_key, raw_key = generate_api_key(integration, "Prod")

    assert raw_key.startswith("clk_")
    assert api_key.key_prefix == raw_key[:12]
    assert api_key.key_hash != raw_key
    assert raw_key not in api_key.key_hash


@pytest.mark.django_db
def test_verify_api_key_succeeds_with_correct_raw_key(integration):
    api_key, raw_key = generate_api_key(integration, "Prod")

    verified = verify_api_key(raw_key)

    assert verified is not None
    assert verified.pk == api_key.pk
    verified.refresh_from_db()
    assert verified.last_used_at is not None


@pytest.mark.django_db
def test_verify_api_key_fails_with_wrong_key(integration):
    generate_api_key(integration, "Prod")
    assert verify_api_key("clk_totally-wrong-key-value") is None


@pytest.mark.django_db
def test_verify_api_key_fails_for_revoked_key(integration):
    api_key, raw_key = generate_api_key(integration, "Prod")
    revoke_api_key(api_key)

    assert verify_api_key(raw_key) is None


@pytest.mark.django_db
def test_verify_api_key_fails_for_expired_key(integration):
    from datetime import timedelta

    from django.utils import timezone

    api_key, raw_key = generate_api_key(integration, "Prod", expires_at=timezone.now() - timedelta(days=1))

    assert verify_api_key(raw_key) is None


@pytest.mark.django_db
def test_rotate_api_key_invalidates_old_key_and_issues_new_one(integration):
    api_key, old_raw_key = generate_api_key(integration, "Prod")

    _, new_raw_key = rotate_api_key(api_key)

    assert verify_api_key(old_raw_key) is None
    assert verify_api_key(new_raw_key) is not None
    assert new_raw_key != old_raw_key


@pytest.mark.django_db
def test_rotate_api_key_rejects_revoked_key(integration):
    api_key, _ = generate_api_key(integration, "Prod")
    revoke_api_key(api_key)

    with pytest.raises(ValueError):
        rotate_api_key(api_key)


@pytest.mark.django_db
def test_revoke_api_key_sets_revoked_at_and_deactivates(api_key):
    revoke_api_key(api_key)
    api_key.refresh_from_db()
    assert api_key.revoked_at is not None
    assert api_key.is_active is False


@pytest.mark.django_db
def test_revoke_api_key_rejects_already_revoked(api_key):
    revoke_api_key(api_key)
    with pytest.raises(ValueError):
        revoke_api_key(api_key)


@pytest.mark.django_db
def test_create_webhook_endpoint_generates_secret(integration):
    endpoint = create_webhook_endpoint(integration, "https://example.com/hooks")
    assert endpoint.secret
    assert len(endpoint.secret) > 20


@pytest.mark.django_db
def test_regenerate_webhook_secret_changes_the_secret(webhook_endpoint):
    old_secret = webhook_endpoint.secret
    regenerate_webhook_secret(webhook_endpoint)
    webhook_endpoint.refresh_from_db()
    assert webhook_endpoint.secret != old_secret


@pytest.mark.django_db
def test_deliver_webhook_success_marks_delivered(webhook_endpoint):
    def fake_send(url, payload_bytes, signature):
        return 200

    delivery = deliver_webhook(webhook_endpoint, "lead.created", {"id": 1}, send_func=fake_send)

    assert delivery.status == WebhookDelivery.Status.DELIVERED
    assert delivery.response_status_code == 200
    assert delivery.delivered_at is not None
    assert delivery.attempt_count == 1


@pytest.mark.django_db
def test_deliver_webhook_failure_marks_failed_and_schedules_retry(webhook_endpoint):
    def failing_send(url, payload_bytes, signature):
        raise RuntimeError("connection refused")

    delivery = deliver_webhook(webhook_endpoint, "lead.created", {"id": 1}, send_func=failing_send)

    assert delivery.status == WebhookDelivery.Status.FAILED
    assert delivery.error_message == "connection refused"
    assert delivery.next_retry_at is not None
    assert delivery.attempt_count == 1


@pytest.mark.django_db
def test_deliver_webhook_signs_payload_correctly(webhook_endpoint):
    captured = {}

    def capturing_send(url, payload_bytes, signature):
        captured["url"] = url
        captured["payload_bytes"] = payload_bytes
        captured["signature"] = signature
        return 200

    deliver_webhook(webhook_endpoint, "lead.created", {"id": 42}, send_func=capturing_send)

    assert captured["url"] == webhook_endpoint.url
    assert verify_webhook_signature(webhook_endpoint.secret, captured["payload_bytes"], captured["signature"])


@pytest.mark.django_db
def test_schedule_retry_uses_exponential_backoff(webhook_endpoint):
    from django.utils import timezone

    delivery = WebhookDelivery.objects.create(endpoint=webhook_endpoint, event_type="x", attempt_count=0)
    before = timezone.now()

    schedule_retry(delivery)

    assert delivery.next_retry_at > before
    # attempt_count=0 -> 2**0 = 1 minute delay (a loose bound, not exact timing)
    assert delivery.next_retry_at <= before + __import__("datetime").timedelta(minutes=2)


@pytest.mark.django_db
def test_schedule_retry_caps_at_max_delay(webhook_endpoint):
    from datetime import timedelta

    from django.utils import timezone

    delivery = WebhookDelivery.objects.create(endpoint=webhook_endpoint, event_type="x", attempt_count=20)
    before = timezone.now()

    schedule_retry(delivery)

    assert delivery.next_retry_at <= before + timedelta(minutes=61)
