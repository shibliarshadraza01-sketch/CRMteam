"""CP18: URL routes for the integrations API, mounted at
/api/v1/integrations/ by config/urls.py.

    GET/POST          /api/v1/integrations/integrations/
    GET/PATCH/DELETE  /api/v1/integrations/integrations/<id>/
    POST              /api/v1/integrations/integrations/<id>/restore/       (CP7 mixin)
    POST              /api/v1/integrations/integrations/<id>/hard-delete/   (CP7 mixin)

    POST              /api/v1/integrations/api-keys/                (generates + returns raw key once)
    GET               /api/v1/integrations/api-keys/
    GET/PATCH/DELETE  /api/v1/integrations/api-keys/<id>/
    POST              /api/v1/integrations/api-keys/<id>/restore/
    POST              /api/v1/integrations/api-keys/<id>/hard-delete/
    POST              /api/v1/integrations/api-keys/<id>/rotate/     (returns new raw key once)
    POST              /api/v1/integrations/api-keys/<id>/revoke/

    GET/POST          /api/v1/integrations/webhook-endpoints/
    GET/PATCH/DELETE  /api/v1/integrations/webhook-endpoints/<id>/
    POST              /api/v1/integrations/webhook-endpoints/<id>/restore/
    POST              /api/v1/integrations/webhook-endpoints/<id>/hard-delete/
    POST              /api/v1/integrations/webhook-endpoints/<id>/regenerate-secret/
    POST              /api/v1/integrations/webhook-endpoints/<id>/deliver/

    GET               /api/v1/integrations/webhook-deliveries/            (read-only)
    GET               /api/v1/integrations/webhook-deliveries/<id>/

Built entirely from DRF's ``DefaultRouter``.
"""
from rest_framework.routers import DefaultRouter

from .views import APIKeyViewSet, IntegrationViewSet, WebhookDeliveryViewSet, WebhookEndpointViewSet

app_name = "integrations"

router = DefaultRouter()
router.register("integrations", IntegrationViewSet, basename="integration")
router.register("api-keys", APIKeyViewSet, basename="api-key")
router.register("webhook-endpoints", WebhookEndpointViewSet, basename="webhook-endpoint")
router.register("webhook-deliveries", WebhookDeliveryViewSet, basename="webhook-delivery")

urlpatterns = router.urls
