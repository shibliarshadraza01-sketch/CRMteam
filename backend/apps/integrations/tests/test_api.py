"""CP18: end-to-end tests for the integrations API. Requires a real
database.
"""
import pytest

from apps.integrations.models import APIKey, Integration, WebhookDelivery

pytestmark = pytest.mark.django_db

INTEGRATIONS_URL = "/api/v1/integrations/integrations/"
API_KEYS_URL = "/api/v1/integrations/api-keys/"
WEBHOOK_ENDPOINTS_URL = "/api/v1/integrations/webhook-endpoints/"
WEBHOOK_DELIVERIES_URL = "/api/v1/integrations/webhook-deliveries/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# Integration CRUD + ownership scoping
# --------------------------------------------------------------------------


def test_unauthenticated_denied(api_client):
    response = api_client.get(INTEGRATIONS_URL)
    assert response.status_code == 401


def test_employee_can_create_and_owns_it_by_default(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(INTEGRATIONS_URL, {"name": "Zapier"})
    assert response.status_code == 201
    assert response.data["owner"] == employee.id


def test_employee_cannot_see_another_employees_integration(api_client, employee, other_employee):
    Integration.objects.create(name="Not mine", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(INTEGRATIONS_URL)

    assert response.data["count"] == 0


# --------------------------------------------------------------------------
# API key generation/rotation/revocation
# --------------------------------------------------------------------------


def test_generate_api_key_returns_raw_key_once(api_client, employee, integration):
    api_client.force_authenticate(employee)
    response = api_client.post(API_KEYS_URL, {"integration": integration.pk, "name": "Prod"})
    assert response.status_code == 201
    assert response.data["raw_key"].startswith("clk_")
    assert "key_hash" not in response.data


def test_list_api_keys_never_exposes_raw_key_or_hash(api_client, employee, api_key):
    api_client.force_authenticate(employee)
    response = api_client.get(API_KEYS_URL)
    row = response.data["results"][0]
    assert "raw_key" not in row
    assert "key_hash" not in row
    assert row["key_prefix"] == api_key.key_prefix


def test_rotate_action_returns_new_raw_key(api_client, employee, api_key):
    api_client.force_authenticate(employee)
    response = api_client.post(f"{_detail(API_KEYS_URL, api_key.pk)}rotate/")
    assert response.status_code == 200
    assert response.data["raw_key"].startswith("clk_")
    assert response.data["key_prefix"] != api_key.key_prefix


def test_revoke_action_deactivates_key(api_client, employee, api_key):
    api_client.force_authenticate(employee)
    response = api_client.post(f"{_detail(API_KEYS_URL, api_key.pk)}revoke/")
    assert response.status_code == 200
    assert response.data["is_active"] is False
    assert response.data["revoked_at"] is not None


def test_revoke_action_rejects_already_revoked(api_client, employee, api_key):
    api_client.force_authenticate(employee)
    api_client.post(f"{_detail(API_KEYS_URL, api_key.pk)}revoke/")

    response = api_client.post(f"{_detail(API_KEYS_URL, api_key.pk)}revoke/")

    assert response.status_code == 400


def test_rotate_action_rejects_revoked_key(api_client, employee, api_key):
    api_client.force_authenticate(employee)
    api_client.post(f"{_detail(API_KEYS_URL, api_key.pk)}revoke/")

    response = api_client.post(f"{_detail(API_KEYS_URL, api_key.pk)}rotate/")

    assert response.status_code == 400


def test_employee_cannot_see_another_employees_api_keys(api_client, employee, other_employee):
    other_integration = Integration.objects.create(name="Theirs", owner=other_employee)
    from apps.integrations.services import generate_api_key

    generate_api_key(other_integration, "Their key")
    api_client.force_authenticate(employee)

    response = api_client.get(API_KEYS_URL)

    assert response.data["count"] == 0


# --------------------------------------------------------------------------
# Webhook endpoints + delivery
# --------------------------------------------------------------------------


def test_create_webhook_endpoint_generates_secret(api_client, employee, integration):
    api_client.force_authenticate(employee)
    response = api_client.post(
        WEBHOOK_ENDPOINTS_URL, {"integration": integration.pk, "url": "https://example.com/hooks"}
    )
    assert response.status_code == 201
    assert response.data["secret"]


def test_regenerate_secret_action_changes_secret(api_client, employee, webhook_endpoint):
    old_secret = webhook_endpoint.secret
    api_client.force_authenticate(employee)

    response = api_client.post(f"{_detail(WEBHOOK_ENDPOINTS_URL, webhook_endpoint.pk)}regenerate-secret/")

    assert response.status_code == 200
    assert response.data["secret"] != old_secret


def test_deliver_action_creates_delivery(api_client, employee, webhook_endpoint, monkeypatch):
    monkeypatch.setattr("apps.integrations.services._default_send_func", lambda url, body, sig: 200)
    api_client.force_authenticate(employee)

    response = api_client.post(
        f"{_detail(WEBHOOK_ENDPOINTS_URL, webhook_endpoint.pk)}deliver/",
        {"event_type": "lead.created", "payload": {"id": 1}},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == "DELIVERED"
    assert WebhookDelivery.objects.filter(endpoint=webhook_endpoint).exists()


def test_deliver_action_requires_event_type(api_client, employee, webhook_endpoint):
    api_client.force_authenticate(employee)
    response = api_client.post(f"{_detail(WEBHOOK_ENDPOINTS_URL, webhook_endpoint.pk)}deliver/", {})
    assert response.status_code == 400


def test_webhook_delivery_has_no_create_endpoint(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(WEBHOOK_DELIVERIES_URL, {"endpoint": 1})
    assert response.status_code == 405


def test_employee_sees_only_deliveries_of_their_own_endpoints(api_client, employee, other_employee):
    from apps.integrations.services import create_integration, create_webhook_endpoint, deliver_webhook

    mine_integration = create_integration("Mine", owner=employee)
    theirs_integration = create_integration("Theirs", owner=other_employee)
    mine_endpoint = create_webhook_endpoint(mine_integration, "https://a.example.com")
    theirs_endpoint = create_webhook_endpoint(theirs_integration, "https://b.example.com")
    deliver_webhook(mine_endpoint, "x", {}, send_func=lambda url, body, sig: 200)
    deliver_webhook(theirs_endpoint, "x", {}, send_func=lambda url, body, sig: 200)
    api_client.force_authenticate(employee)

    response = api_client.get(WEBHOOK_DELIVERIES_URL)

    assert response.data["count"] == 1


# --------------------------------------------------------------------------
# Search / pagination
# --------------------------------------------------------------------------


def test_search_integrations_by_name(api_client, employee):
    Integration.objects.create(name="Zapier Connector", owner=employee)
    Integration.objects.create(name="Other", owner=employee)

    api_client.force_authenticate(employee)
    response = api_client.get(INTEGRATIONS_URL, {"search": "Zapier"})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Zapier Connector"}


def test_pagination_default_page_size_is_20(api_client, employee):
    for i in range(25):
        Integration.objects.create(name=f"Integration {i:03d}", owner=employee)
    api_client.force_authenticate(employee)

    response = api_client.get(INTEGRATIONS_URL)

    assert len(response.data["results"]) == 20
    assert response.data["count"] == 25
