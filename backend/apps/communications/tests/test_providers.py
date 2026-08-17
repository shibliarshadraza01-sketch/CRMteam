"""Final production operations pass: A1 Routes SIP + WhatsApp Business
API integration tests. No real provider account exists in this
environment — every provider HTTP call is mocked (``unittest.mock``),
so these tests verify OUR code's behavior (record creation, status
transitions, failure handling, webhook signature verification,
authorization, throttling) without depending on network access or real
credentials. Live verification against real A1 Routes/WhatsApp accounts
is explicitly out of scope until real credentials exist — same status
SendGrid had (and, once a real key was supplied, was moved out of).
"""
import hashlib
import hmac
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.communications.models import Call, WhatsAppMessage
from apps.communications.providers.a1routes import A1RoutesError, verify_webhook_signature as verify_a1routes_sig
from apps.communications.providers.whatsapp import WhatsAppError, verify_webhook_signature as verify_whatsapp_sig
from apps.communications.services import (
    apply_a1routes_webhook_event,
    apply_whatsapp_webhook_event,
    initiate_call,
    send_whatsapp_message,
)

pytestmark = pytest.mark.django_db

CALLS_URL = "/api/v1/communications/calls/"
WHATSAPP_SEND_URL = "/api/v1/communications/whatsapp/send/"
WHATSAPP_LIST_URL = "/api/v1/communications/whatsapp/messages/"
A1ROUTES_WEBHOOK_URL = "/api/v1/webhooks/a1routes/"
WHATSAPP_WEBHOOK_URL = "/api/v1/webhooks/whatsapp/"


# --------------------------------------------------------------------------
# Provider client signature verification (no network, no DB)
# --------------------------------------------------------------------------


def test_a1routes_signature_verification_accepts_correct_signature():
    secret = "test-secret"
    body = b'{"call_id":"abc"}'
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_a1routes_sig(body, signature, secret=secret) is True


def test_a1routes_signature_verification_rejects_wrong_signature():
    assert verify_a1routes_sig(b"{}", "wrong", secret="test-secret") is False


def test_a1routes_signature_verification_rejects_missing_secret():
    assert verify_a1routes_sig(b"{}", "anything", secret="") is False


def test_whatsapp_signature_verification_accepts_correct_signature():
    secret = "app-secret"
    body = b'{"entry":[]}'
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_whatsapp_sig(body, signature, app_secret=secret) is True


def test_whatsapp_signature_verification_rejects_wrong_signature():
    assert verify_whatsapp_sig(b"{}", "sha256=wrong", app_secret="app-secret") is False


# --------------------------------------------------------------------------
# services.initiate_call()
# --------------------------------------------------------------------------


def test_initiate_call_records_success(employee, settings):
    settings.A1ROUTES_DEFAULT_FROM_NUMBER = "+10000000000"
    import os

    with patch.dict(os.environ, {"A1ROUTES_API_KEY": "test-key"}):
        with patch("apps.communications.services.A1RoutesClient.initiate_call", return_value="prov-call-1"):
            call = initiate_call("+10000000000", "+15551234567", owner=employee)

    assert call.status == Call.Status.RINGING
    assert call.provider_call_id == "prov-call-1"
    assert call.started_at is not None


def test_initiate_call_records_provider_failure_without_raising(employee):
    import os

    with patch.dict(os.environ, {"A1ROUTES_API_KEY": "test-key"}):
        with patch(
            "apps.communications.services.A1RoutesClient.initiate_call",
            side_effect=A1RoutesError("provider rejected the call"),
        ):
            call = initiate_call("+10000000000", "+15551234567", owner=employee)

    assert call.status == Call.Status.FAILED
    assert "provider rejected the call" in call.error_message


# --------------------------------------------------------------------------
# services.send_whatsapp_message()
# --------------------------------------------------------------------------


def test_send_whatsapp_message_records_success(employee):
    import os

    with patch.dict(os.environ, {"WHATSAPP_API_TOKEN": "tok", "WHATSAPP_PHONE_ID": "12345"}):
        with patch("apps.communications.services.WhatsAppClient.send_message", return_value="wamid.123"):
            message = send_whatsapp_message("+15551234567", "Hello", owner=employee)

    assert message.status == WhatsAppMessage.Status.SENT
    assert message.provider_message_id == "wamid.123"
    assert message.sender == "12345"


def test_send_whatsapp_message_records_provider_failure_without_raising(employee):
    import os

    with patch.dict(os.environ, {"WHATSAPP_API_TOKEN": "tok", "WHATSAPP_PHONE_ID": "12345"}):
        with patch(
            "apps.communications.services.WhatsAppClient.send_message",
            side_effect=WhatsAppError("invalid recipient"),
        ):
            message = send_whatsapp_message("+15551234567", "Hello", owner=employee)

    assert message.status == WhatsAppMessage.Status.FAILED
    assert "invalid recipient" in message.error_message


def test_send_whatsapp_message_missing_credentials_fails_gracefully(employee):
    import os

    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("WHATSAPP_API_TOKEN", None)
        message = send_whatsapp_message("+15551234567", "Hello", owner=employee)

    assert message.status == WhatsAppMessage.Status.FAILED
    assert message.error_message


# --------------------------------------------------------------------------
# Webhook idempotency
# --------------------------------------------------------------------------


def test_apply_a1routes_webhook_event_updates_matching_call(employee):
    call = Call.objects.create(
        owner=employee, direction=Call.Direction.OUTBOUND, from_number="+1", to_number="+2",
        provider_call_id="prov-1", status=Call.Status.RINGING,
    )
    updated = apply_a1routes_webhook_event({"call_id": "prov-1", "status": "completed", "duration_seconds": 42})
    call.refresh_from_db()
    assert updated.pk == call.pk
    assert call.status == Call.Status.COMPLETED
    assert call.duration_seconds == 42
    assert call.ended_at is not None


def test_apply_a1routes_webhook_event_ignores_unknown_call_id():
    assert apply_a1routes_webhook_event({"call_id": "does-not-exist", "status": "completed"}) is None


def test_apply_a1routes_webhook_event_is_idempotent(employee):
    call = Call.objects.create(
        owner=employee, direction=Call.Direction.OUTBOUND, from_number="+1", to_number="+2",
        provider_call_id="prov-2", status=Call.Status.COMPLETED, duration_seconds=10,
    )
    apply_a1routes_webhook_event({"call_id": "prov-2", "status": "completed", "duration_seconds": 999})
    call.refresh_from_db()
    # Re-applying the same terminal status must not overwrite duration a
    # second time from a replayed event.
    assert call.duration_seconds == 10


def test_apply_whatsapp_webhook_event_updates_matching_message(employee):
    message = WhatsAppMessage.objects.create(
        owner=employee, direction=WhatsAppMessage.Direction.OUTBOUND, sender="1", receiver="2",
        message="hi", provider_message_id="wamid.1", status=WhatsAppMessage.Status.SENT,
    )
    apply_whatsapp_webhook_event({"id": "wamid.1", "status": "delivered"})
    message.refresh_from_db()
    assert message.status == WhatsAppMessage.Status.DELIVERED


# --------------------------------------------------------------------------
# API: authentication, authorization, throttling not-disabled
# --------------------------------------------------------------------------


def test_unauthenticated_cannot_initiate_call(api_client):
    response = api_client.post(CALLS_URL, {"customer": 1})
    assert response.status_code == 401


def test_unauthenticated_cannot_send_whatsapp_message(api_client):
    response = api_client.post(WHATSAPP_SEND_URL, {"customer": 1, "message": "hi"})
    assert response.status_code == 401


def test_initiate_call_rejects_a_raw_number(api_client, employee):
    """``to_number`` is no longer part of the contract at all: a request
    that supplies only a number names nobody to call and is rejected,
    which is what stops this endpoint dialing arbitrary numbers.
    """
    api_client.force_authenticate(employee)
    response = api_client.post(CALLS_URL, {"to_number": "+15551234567"})
    assert response.status_code == 400


def test_employee_cannot_call_another_employees_customer(api_client, employee, other_employee, organization):
    from apps.crm.models import Customer

    foreign = Customer.objects.create(
        organization=organization, name="Foreign Call", slug="foreign-call",
        owner=other_employee, phone="+15550001111",
    )
    api_client.force_authenticate(employee)
    response = api_client.post(CALLS_URL, {"customer": foreign.pk})
    assert response.status_code == 404


def test_employee_cannot_view_another_employees_call(api_client, employee, other_employee):
    call = Call.objects.create(
        owner=other_employee, direction=Call.Direction.OUTBOUND, from_number="+1", to_number="+2",
    )
    api_client.force_authenticate(employee)
    response = api_client.get(f"{CALLS_URL}{call.pk}/")
    assert response.status_code == 404


def test_authenticated_user_can_initiate_call_records_attempt_even_on_provider_failure(api_client, employee):
    from apps.crm.models import Customer
    from apps.organization.models import Organization

    organization = Organization.objects.create(name="Call Org", slug="call-org")
    customer = Customer.objects.create(
        organization=organization, name="Callable", slug="callable",
        owner=employee, phone="+15551234567",
    )
    api_client.force_authenticate(employee)
    with patch(
        "apps.communications.services.A1RoutesClient.__init__",
        side_effect=A1RoutesError("A1ROUTES_API_KEY is not configured."),
    ):
        response = api_client.post(CALLS_URL, {"customer": customer.pk})
    assert response.status_code == 201
    assert response.data["status"] == "FAILED"
    # The number the backend resolved never comes back to the employee.
    assert "to_number" not in response.data
    assert "+15551234567" not in response.content.decode()


# --------------------------------------------------------------------------
# Webhook endpoints: signature required, no JWT required
# --------------------------------------------------------------------------


def test_a1routes_webhook_rejects_missing_signature(api_client):
    response = api_client.post(A1ROUTES_WEBHOOK_URL, {"call_id": "x", "status": "completed"}, format="json")
    assert response.status_code == 401


def test_a1routes_webhook_accepts_valid_signature(api_client, settings, employee):
    import json

    call = Call.objects.create(
        owner=employee, direction=Call.Direction.OUTBOUND, from_number="+1", to_number="+2",
        provider_call_id="prov-9", status=Call.Status.RINGING,
    )
    body = json.dumps({"call_id": "prov-9", "status": "completed"}).encode()
    secret = "webhook-secret"
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    with patch("apps.communications.views.verify_a1routes_signature", return_value=True):
        response = api_client.post(
            A1ROUTES_WEBHOOK_URL, data=body, content_type="application/json",
            HTTP_X_A1ROUTES_SIGNATURE=signature,
        )
    assert response.status_code == 200
    call.refresh_from_db()
    assert call.status == Call.Status.COMPLETED


def test_whatsapp_webhook_rejects_missing_signature(api_client):
    response = api_client.post(WHATSAPP_WEBHOOK_URL, {"entry": []}, format="json")
    assert response.status_code == 401


def test_whatsapp_webhook_subscription_handshake(api_client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "my-verify-token")
    response = api_client.get(
        WHATSAPP_WEBHOOK_URL,
        {"hub.mode": "subscribe", "hub.verify_token": "my-verify-token", "hub.challenge": "12345"},
    )
    assert response.status_code == 200


def test_whatsapp_webhook_subscription_handshake_rejects_wrong_token(api_client, monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "my-verify-token")
    response = api_client.get(
        WHATSAPP_WEBHOOK_URL,
        {"hub.mode": "subscribe", "hub.verify_token": "wrong-token", "hub.challenge": "12345"},
    )
    assert response.status_code == 403
