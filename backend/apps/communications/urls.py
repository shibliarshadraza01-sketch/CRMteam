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

    POST              /api/v1/communications/whatsapp/send/         (WhatsApp Business API)
    GET               /api/v1/communications/whatsapp/messages/
    GET               /api/v1/communications/whatsapp/messages/<id>/

Inbound provider webhooks (``/api/v1/webhooks/...``) are mounted
separately by ``config/urls.py`` — see that module and
``views.A1RoutesWebhookView``/``views.WhatsAppWebhookView``'s own
docstrings for why they live outside the versioned, JWT-authenticated
``/api/v1/communications/`` namespace.

Built entirely from DRF's ``DefaultRouter`` for the REST-shaped
resources; the WhatsApp send/list split uses explicit ``path()`` entries
since ``send``/``messages`` aren't a router's default list/create verbs
on the same URL.
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CallViewSet,
    CommunicationLogViewSet,
    EmailMessageViewSet,
    EmailTemplateViewSet,
    NotificationViewSet,
    WhatsAppMessageViewSet,
)

app_name = "communications"

router = DefaultRouter()
router.register("email-templates", EmailTemplateViewSet, basename="email-template")
router.register("email-messages", EmailMessageViewSet, basename="email-message")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("communication-logs", CommunicationLogViewSet, basename="communication-log")
router.register("calls", CallViewSet, basename="call")

urlpatterns = router.urls + [
    path(
        "whatsapp/send/",
        WhatsAppMessageViewSet.as_view({"post": "create"}),
        name="whatsapp-send",
    ),
    path(
        "whatsapp/messages/",
        WhatsAppMessageViewSet.as_view({"get": "list"}),
        name="whatsapp-message-list",
    ),
    path(
        "whatsapp/messages/<int:pk>/",
        WhatsAppMessageViewSet.as_view({"get": "retrieve"}),
        name="whatsapp-message-detail",
    ),
]
