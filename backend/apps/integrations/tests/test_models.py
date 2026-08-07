"""CP18: tests for apps/integrations/models.py."""
import pytest

from apps.integrations.models import APIKey, Integration, WebhookDelivery, WebhookEndpoint

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_integration_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in Integration._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_integration_str_returns_name():
    assert str(Integration(name="Zapier")) == "Zapier"


def test_apikey_has_no_raw_key_field():
    """Only key_prefix (plaintext, safe) and key_hash (one-way) are real
    model fields — there is no field that could ever hold the raw key.
    """
    field_names = {f.name for f in APIKey._meta.get_fields()}
    assert "key_prefix" in field_names
    assert "key_hash" in field_names
    assert "raw_key" not in field_names
    assert "key" not in field_names


def test_apikey_str_includes_name_and_prefix():
    assert str(APIKey(name="Prod", key_prefix="clk_abcd1234")) == "Prod (clk_abcd1234)"


def test_apikey_owner_property_delegates_to_integration_owner():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="owner@example.com")
    integration = Integration(name="I", owner=user)
    api_key = APIKey(integration=integration)
    assert api_key.owner is user


def test_apikey_is_expired_false_when_no_expiry():
    assert APIKey(expires_at=None).is_expired is False


def test_apikey_is_expired_true_when_in_past():
    from django.utils import timezone

    assert APIKey(expires_at=timezone.now() - __import__("datetime").timedelta(days=1)).is_expired is True


def test_apikey_is_revoked_reflects_revoked_at():
    assert APIKey(revoked_at=None).is_revoked is False
    from django.utils import timezone

    assert APIKey(revoked_at=timezone.now()).is_revoked is True


def test_webhookendpoint_str_returns_url():
    assert str(WebhookEndpoint(url="https://example.com/hooks")) == "https://example.com/hooks"


def test_webhookendpoint_owner_property_delegates_to_integration_owner():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="owner2@example.com")
    integration = Integration(name="I", owner=user)
    endpoint = WebhookEndpoint(integration=integration)
    assert endpoint.owner is user


def test_webhookdelivery_owner_property_delegates_two_levels_deep():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="owner3@example.com")
    integration = Integration(name="I", owner=user)
    endpoint = WebhookEndpoint(integration=integration)
    delivery = WebhookDelivery(endpoint=endpoint)
    assert delivery.owner is user


def test_webhookdelivery_status_defaults_to_pending():
    assert WebhookDelivery._meta.get_field("status").default == WebhookDelivery.Status.PENDING


def test_webhookdelivery_str_includes_event_type_url_and_status():
    endpoint = WebhookEndpoint(url="https://example.com/hooks")
    delivery = WebhookDelivery(endpoint=endpoint, event_type="lead.created", status=WebhookDelivery.Status.PENDING)
    assert "lead.created" in str(delivery)
    assert "https://example.com/hooks" in str(delivery)
    assert "PENDING" in str(delivery)


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_integration_create_and_retrieve(employee):
    integ = Integration.objects.create(name="Draft", owner=employee)
    assert Integration.objects.get(pk=integ.pk).is_active is True


@pytest.mark.django_db
def test_apikey_key_prefix_uniqueness_enforced(integration):
    from django.db import IntegrityError

    APIKey.objects.create(integration=integration, name="A", key_prefix="clk_dup", key_hash="x")
    with pytest.raises(IntegrityError):
        APIKey.objects.create(integration=integration, name="B", key_prefix="clk_dup", key_hash="y")


@pytest.mark.django_db
def test_deleting_integration_cascades_to_api_keys_and_endpoints(integration, api_key, webhook_endpoint):
    integration.delete()
    assert not APIKey.objects.filter(pk=api_key.pk).exists()
    assert not WebhookEndpoint.objects.filter(pk=webhook_endpoint.pk).exists()


@pytest.mark.django_db
def test_deleting_webhook_endpoint_cascades_to_deliveries(webhook_endpoint):
    delivery = WebhookDelivery.objects.create(endpoint=webhook_endpoint, event_type="lead.created")
    webhook_endpoint.delete()
    assert not WebhookDelivery.objects.filter(pk=delivery.pk).exists()


@pytest.mark.django_db
def test_integration_manager_has_access_true_for_managed_owner(manager, employee, organization):
    from apps.organization.models import Department, Membership, Team

    department = Department.objects.create(organization=organization, name="Ops")
    team = Team.objects.create(department=department, name="Ops Team", manager=manager)
    Membership.objects.create(team=team, user=employee)

    integration = Integration.objects.create(name="I", owner=employee)

    assert integration.manager_has_access(manager) is True
