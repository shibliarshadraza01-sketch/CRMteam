"""CP15 (+ final production operations pass): URL routes for the
communications API, mounted at /api/v1/communications/ by config/urls.py.

    GET/POST          /api/v1/communications/email-templates/
    GET/PATCH/DELETE  /api/v1/communications/email-templates/<id>/
    POST              /api/v1/communications/email-templates/<id>/restore/       (CP7 mixin)
    POST              /api/v1/communications/email-templates/<id>/hard-delete/   (CP7 mixin)

    GET/POST          /api/v1/communications/email-messages/
    GET/PATCH/DELETE  /api/v1/communications/email-messages/<id>/
    POST              /api/v1/communications/email-messages/<id>/send/

    GET/POST          /api/v1/communications/notifications/
    GET/PATCH/DELETE  /api/v1/communications/notifications/<id>/
    POST              /api/v1/communications/notifications/<id>/mark-read/
    POST              /api/v1/communications/notifications/<id>/mark-unread/

    GET               /api/v1/communications/communication-logs/            (read-only)
    GET               /api/v1/communications/communication-logs/<id>/

    GET/POST          /api/v1/communications/calls/                (A1 Routes SIP)
    GET               /api/v1/communications/calls/<id>/

Inbound provider webhooks (``/api/v1/webhooks/...``) are mounted
separately by ``config/urls.py`` — see that module and
``views.A1RoutesWebhookView``'s own docstring for why it lives outside
the versioned, JWT-authenticated ``/api/v1/communications/`` namespace.

Built entirely from DRF's ``DefaultRouter`` for the REST-shaped
resources.

WhatsApp Business API support (send/messages routes, webhook) was
removed — it was explicitly descoped by the project owner and must not
be reintroduced.
"""
from rest_framework.routers import DefaultRouter

from .views import (
    CallViewSet,
    CommunicationLogViewSet,
    EmailMessageViewSet,
    EmailTemplateViewSet,
    NotificationViewSet,
)

app_name = "communications"

router = DefaultRouter()
router.register("email-templates", EmailTemplateViewSet, basename="email-template")
router.register("email-messages", EmailMessageViewSet, basename="email-message")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("communication-logs", CommunicationLogViewSet, basename="communication-log")
router.register("calls", CallViewSet, basename="call")

urlpatterns = router.urls
