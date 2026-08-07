"""CP18: tests for the querysets on apps/integrations/models.py."""
import pytest

from apps.integrations.models import APIKey, Integration, WebhookDelivery, WebhookEndpoint

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_integration_active_filters_is_deleted_and_is_active_without_hitting_db():
    where_sql = str(Integration.objects.active().query.where)
    assert "is_deleted" in where_sql
    assert "is_active" in where_sql


def test_apikey_active_filters_is_active_and_revoked_without_hitting_db():
    where_sql = str(APIKey.objects.active().query.where)
    assert "is_active" in where_sql
    assert "revoked_at" in where_sql


def test_apikey_for_integration_builds_filter_without_hitting_db():
    integration = Integration(pk=1, name="I")
    assert len(APIKey.objects.for_integration(integration).query.where) > 0


def test_webhookendpoint_for_integration_builds_filter_without_hitting_db():
    integration = Integration(pk=1, name="I")
    assert len(WebhookEndpoint.objects.for_integration(integration).query.where) > 0


def test_webhookdelivery_for_endpoint_builds_filter_without_hitting_db():
    endpoint = WebhookEndpoint(pk=1, url="https://example.com")
    assert len(WebhookDelivery.objects.for_endpoint(endpoint).query.where) > 0


def test_webhookdelivery_due_for_retry_filters_on_status_and_next_retry_at_without_hitting_db():
    where_sql = str(WebhookDelivery.objects.due_for_retry().query.where)
    assert "status" in where_sql
    assert "next_retry_at" in where_sql


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_active_apikey_manager_excludes_inactive_revoked_and_deleted(integration):
    from apps.integrations.services import generate_api_key, revoke_api_key

    active, _ = generate_api_key(integration, "Active")
    revoked, _ = generate_api_key(integration, "Revoked")
    revoke_api_key(revoked)
    deleted, _ = generate_api_key(integration, "Deleted")
    deleted.soft_delete()

    names = set(APIKey.active_objects.values_list("name", flat=True))
    assert names == {"Active"}


@pytest.mark.django_db
def test_webhookendpoint_subscribed_to_matches_real_rows(integration):
    from apps.integrations.services import create_webhook_endpoint

    matching = create_webhook_endpoint(integration, "https://a.example.com", event_types=["lead.created"])
    create_webhook_endpoint(integration, "https://b.example.com", event_types=["opportunity.won"])

    assert list(WebhookEndpoint.objects.subscribed_to("lead.created")) == [matching]


@pytest.mark.django_db
def test_webhookdelivery_due_for_retry_matches_real_rows(webhook_endpoint):
    from datetime import timedelta

    from django.utils import timezone

    due = WebhookDelivery.objects.create(
        endpoint=webhook_endpoint, event_type="x", status=WebhookDelivery.Status.FAILED,
        next_retry_at=timezone.now() - timedelta(minutes=1),
    )
    WebhookDelivery.objects.create(
        endpoint=webhook_endpoint, event_type="x", status=WebhookDelivery.Status.FAILED,
        next_retry_at=timezone.now() + timedelta(minutes=30),
    )
    WebhookDelivery.objects.create(endpoint=webhook_endpoint, event_type="x", status=WebhookDelivery.Status.DELIVERED)

    assert list(WebhookDelivery.objects.due_for_retry()) == [due]
