"""Django admin registrations for the integrations domain.

Every `ModelAdmin` mixes in CP7's `SoftDeleteTimeStampedAdminMixin` —
unfiltered queryset, `is_deleted` in `list_filter`, soft-delete/restore
bulk actions, read-only timestamp/audit fields, all for free.

`APIKey.key_hash` and `WebhookEndpoint.secret` are both marked read-only
here (visible to staff, never hand-editable) — a Django admin user
typing an arbitrary value into either field would bypass
`services.generate_api_key()`'s hashing / `create_webhook_endpoint()`'s
generation entirely, silently breaking the "the hash always corresponds
to a real, once-shown raw key" and "the secret was actually
cryptographically random" guarantees. `services.rotate_api_key()`/
`regenerate_webhook_secret()` remain the only sanctioned way to change
either value, whether reached via the API or a future admin action.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin

from .models import APIKey, Integration, WebhookDelivery, WebhookEndpoint


@admin.register(Integration)
class IntegrationAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "owner", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("name", "description")
    autocomplete_fields = ("owner",)
    ordering = ("name",)


@admin.register(APIKey)
class APIKeyAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "key_prefix", "integration", "is_active", "revoked_at", "is_deleted")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("name", "key_prefix", "integration__name")
    autocomplete_fields = ("integration",)
    ordering = ("-created_at",)

    def get_readonly_fields(self, request, obj=None):
        return list(super().get_readonly_fields(request, obj)) + ["key_hash", "key_prefix"]


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("url", "integration", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("url", "integration__name")
    autocomplete_fields = ("integration",)
    ordering = ("-created_at",)

    def get_readonly_fields(self, request, obj=None):
        return list(super().get_readonly_fields(request, obj)) + ["secret"]


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("event_type", "endpoint", "status", "attempt_count", "created_at", "is_deleted")
    list_filter = ("status", "is_deleted")
    search_fields = ("event_type", "endpoint__url")
    autocomplete_fields = ("endpoint",)
    ordering = ("-created_at",)
