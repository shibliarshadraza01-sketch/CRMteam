"""CP18: tests for apps/integrations/admin.py. Django's admin registry is
populated at import time — no database needed.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin
from apps.integrations.admin import (
    APIKeyAdmin,
    IntegrationAdmin,
    WebhookDeliveryAdmin,
    WebhookEndpointAdmin,
)
from apps.integrations.models import APIKey, Integration, WebhookDelivery, WebhookEndpoint


def test_all_four_models_are_registered():
    assert Integration in admin.site._registry
    assert APIKey in admin.site._registry
    assert WebhookEndpoint in admin.site._registry
    assert WebhookDelivery in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[Integration], IntegrationAdmin)
    assert isinstance(admin.site._registry[APIKey], APIKeyAdmin)
    assert isinstance(admin.site._registry[WebhookEndpoint], WebhookEndpointAdmin)
    assert isinstance(admin.site._registry[WebhookDelivery], WebhookDeliveryAdmin)


def test_every_integrations_admin_uses_soft_delete_timestamped_mixin():
    for admin_class in (IntegrationAdmin, APIKeyAdmin, WebhookEndpointAdmin, WebhookDeliveryAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_apikey_admin_marks_key_hash_and_prefix_readonly():
    admin_instance = admin.site._registry[APIKey]
    readonly = admin_instance.get_readonly_fields(request=None, obj=None)
    assert "key_hash" in readonly
    assert "key_prefix" in readonly


def test_webhookendpoint_admin_marks_secret_readonly():
    admin_instance = admin.site._registry[WebhookEndpoint]
    readonly = admin_instance.get_readonly_fields(request=None, obj=None)
    assert "secret" in readonly


def test_admins_declare_search_fields():
    for model in (Integration, APIKey, WebhookEndpoint, WebhookDelivery):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
