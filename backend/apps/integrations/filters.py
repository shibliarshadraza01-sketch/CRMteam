"""CP18: django-filter ``FilterSet`` classes for the integrations API."""
import django_filters

from .models import APIKey, Integration, WebhookDelivery, WebhookEndpoint


class IntegrationFilterSet(django_filters.FilterSet):
    class Meta:
        model = Integration
        fields = ["owner", "is_active"]


class APIKeyFilterSet(django_filters.FilterSet):
    class Meta:
        model = APIKey
        fields = ["integration", "is_active"]


class WebhookEndpointFilterSet(django_filters.FilterSet):
    class Meta:
        model = WebhookEndpoint
        fields = ["integration", "is_active"]


class WebhookDeliveryFilterSet(django_filters.FilterSet):
    class Meta:
        model = WebhookDelivery
        fields = ["endpoint", "status", "event_type"]
