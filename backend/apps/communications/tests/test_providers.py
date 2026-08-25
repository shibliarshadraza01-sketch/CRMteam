"""Final production operations pass: A1 Routes SIP integration tests.
No real provider account exists in this environment — every provider
HTTP call is mocked (``unittest.mock``), so these tests verify OUR
code's behavior (record creation, status transitions, failure handling,
webhook signature verification, authorization, throttling) without
depending on network access or real credentials. Live verification
against a real A1 Routes account is explicitly out of scope until real
credentials exist — same status SendGrid had (and, once a real key was
supplied, was moved out of).

WhatsApp Business API provider tests were removed along with the rest of
the WhatsApp integration (explicitly descoped by the project owner).
"""
import hashlib
import hmac
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.communications.models import Call
from apps.communications.providers.a1routes import A1RoutesError, verify_webhook_signature as verify_a1routes_sig
from apps.communications.services import (
    apply_a1routes_webhook_event,
    initiate_call,
)

pytestmark = pytest.mark.django_db

CALLS_URL = "/api/v1/communications/calls/"
A1ROUTES_WEBHOOK_URL = "/api/v1/webhooks/a1routes/"


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


# --------------------------------------------------------------------------
# API: authentication, authorization, throttling not-disabled
# --------------------------------------------------------------------------


def test_unauthenticated_cannot_initiate_call(api_client):
    response = api_client.post(CALLS_URL, {"customer": 1})
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
