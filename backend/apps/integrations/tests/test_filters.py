"""CP18: tests for apps/integrations/filters.py."""
import pytest

from apps.integrations.filters import APIKeyFilterSet, WebhookDeliveryFilterSet
from apps.integrations.models import APIKey, WebhookDelivery

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_apikey_filterset_declares_expected_fields():
    assert set(APIKeyFilterSet.Meta.fields) == {"integration", "is_active"}


def test_webhookdelivery_filterset_declares_expected_fields():
    assert set(WebhookDeliveryFilterSet.Meta.fields) == {"endpoint", "status", "event_type"}


def test_is_active_filter_builds_query_without_hitting_db():
    filterset = APIKeyFilterSet(data={"is_active": "true"}, queryset=APIKey.objects.all())
    assert filterset.is_valid()
    assert len(filterset.qs.query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_is_active_filter_matches_real_rows(integration):
    from apps.integrations.services import generate_api_key, revoke_api_key

    active, _ = generate_api_key(integration, "Active")
    revoked, _ = generate_api_key(integration, "Revoked")
    revoke_api_key(revoked)

    filterset = APIKeyFilterSet(data={"is_active": "true"}, queryset=APIKey.objects.all())

    assert list(filterset.qs) == [active]


@pytest.mark.django_db
def test_status_filter_matches_real_rows(webhook_endpoint):
    delivered = WebhookDelivery.objects.create(
        endpoint=webhook_endpoint, event_type="x", status=WebhookDelivery.Status.DELIVERED
    )
    WebhookDelivery.objects.create(endpoint=webhook_endpoint, event_type="y", status=WebhookDelivery.Status.FAILED)

    filterset = WebhookDeliveryFilterSet(data={"status": "DELIVERED"}, queryset=WebhookDelivery.objects.all())

    assert list(filterset.qs) == [delivered]
