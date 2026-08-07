"""CP18: tests for apps/integrations/serializers.py."""
import pytest

from apps.integrations.serializers import (
    APIKeySerializer,
    APIKeyWithSecretSerializer,
    IntegrationSerializer,
    WebhookDeliverySerializer,
    WebhookEndpointSerializer,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_integration_serializer_fields():
    fields = IntegrationSerializer().fields
    assert {
        "id", "name", "description", "owner", "is_active",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_apikey_serializer_never_exposes_key_hash_or_raw_key():
    fields = APIKeySerializer().fields
    assert "key_hash" not in fields
    assert "raw_key" not in fields
    assert "key_prefix" in fields


def test_apikey_serializer_identity_fields_are_read_only():
    fields = APIKeySerializer().fields
    for name in ("key_prefix", "is_active", "last_used_at", "revoked_at"):
        assert fields[name].read_only is True


def test_apikey_with_secret_serializer_adds_raw_key_field():
    fields = APIKeyWithSecretSerializer().fields
    assert "raw_key" in fields
    assert "key_hash" not in fields


def test_apikey_with_secret_serializer_reads_transient_raw_key_attribute():
    class FakeKey:
        pk = 1
        raw_key = "clk_abc123"

    serializer = APIKeyWithSecretSerializer()
    assert serializer.get_raw_key(FakeKey()) == "clk_abc123"


def test_apikey_with_secret_serializer_returns_none_without_transient_attribute():
    class FakeKey:
        pk = 1

    serializer = APIKeyWithSecretSerializer()
    assert serializer.get_raw_key(FakeKey()) is None


def test_webhookendpoint_serializer_exposes_secret_as_read_only():
    fields = WebhookEndpointSerializer().fields
    assert "secret" in fields
    assert fields["secret"].read_only is True


def test_webhookdelivery_serializer_is_entirely_read_only():
    for name, field in WebhookDeliverySerializer().fields.items():
        assert field.read_only is True


# --------------------------------------------------------------------------
# Requires database — full serializer validation (FK fields query the DB)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_integration_serializer_full_validation(employee):
    serializer = IntegrationSerializer(data={"name": "I", "owner": employee.pk})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_apikey_with_secret_serializer_output(integration):
    from apps.integrations.services import generate_api_key

    api_key, raw_key = generate_api_key(integration, "Prod")
    api_key.raw_key = raw_key

    data = APIKeyWithSecretSerializer(api_key).data

    assert data["raw_key"] == raw_key
    assert "key_hash" not in data
