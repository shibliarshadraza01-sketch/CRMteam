"""CP18: serializers for the integrations domain.

Every serializer mixes in CP7's `SoftDeleteTimeStampedSerializerMixin`.

`APIKeySerializer` NEVER exposes `key_hash` — it isn't in `Meta.fields` at
all, not merely marked read-only, so there is no field a client could
even attempt to read or write it through. The one-time raw key is
returned ONLY by `APIKeyWithSecretSerializer`, used exclusively by the
`generate`/`rotate` actions' responses (see `views.py`) — never by
list/retrieve.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.serializers import SoftDeleteTimeStampedSerializerMixin

from .models import APIKey, Integration, WebhookDelivery, WebhookEndpoint


class _IntegrationsSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base: every integrations serializer gets the CP7 timestamp/
    audit/soft-delete field shape without repeating it per class.
    """


class IntegrationSerializer(_IntegrationsSerializer):
    class Meta:
        model = Integration
        fields = [
            "id", "name", "description", "owner", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class APIKeySerializer(_IntegrationsSerializer):
    """List/retrieve shape — `key_prefix` only, never `key_hash`. Business
    fields (`name` aside) are read-only: an `APIKey`'s identity fields are
    entirely managed by `services.py` (`generate_api_key()`/
    `rotate_api_key()`/`revoke_api_key()`), never by a direct PATCH.
    """

    is_expired = serializers.BooleanField(read_only=True)
    is_revoked = serializers.BooleanField(read_only=True)

    class Meta:
        model = APIKey
        fields = [
            "id", "integration", "name", "key_prefix", "is_active", "is_expired", "is_revoked",
            "last_used_at", "expires_at", "revoked_at",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = [
            "key_prefix", "is_active", "last_used_at", "revoked_at",
        ]


class APIKeyWithSecretSerializer(APIKeySerializer):
    """The ONLY serializer that ever carries the raw key — used exclusively
    by `generate`/`rotate` action responses, never by list/retrieve/update.
    `raw_key` is a plain, non-model `SerializerMethodField` reading
    `instance.raw_key` — a transient attribute `views.py` sets on the
    instance just before serializing, never persisted (see `models.py`'s
    `APIKey` docstring: the raw key exists in memory for exactly one
    response, never in the database).
    """

    raw_key = serializers.SerializerMethodField()

    class Meta(APIKeySerializer.Meta):
        fields = APIKeySerializer.Meta.fields + ["raw_key"]

    @extend_schema_field(str)
    def get_raw_key(self, obj):
        return getattr(obj, "raw_key", None)


class WebhookEndpointSerializer(_IntegrationsSerializer):
    """`secret` IS exposed here, on every read — a deliberate difference
    from `APIKeySerializer`; see `models.py`'s `WebhookEndpoint` docstring
    for why a webhook signing secret is a different kind of secret than a
    bearer API key.
    """

    class Meta:
        model = WebhookEndpoint
        fields = [
            "id", "integration", "url", "secret", "event_types", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = ["secret"]


class WebhookDeliverySerializer(_IntegrationsSerializer):
    """Entirely read-only — see `models.py`'s `WebhookDelivery` docstring
    and `views.py`: there is no create endpoint, only list/retrieve
    (deliveries are created exclusively via `services.deliver_webhook()`).
    """

    class Meta:
        model = WebhookDelivery
        fields = [
            "id", "endpoint", "event_type", "payload", "status", "response_status_code",
            "attempt_count", "next_retry_at", "delivered_at", "error_message",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = fields
