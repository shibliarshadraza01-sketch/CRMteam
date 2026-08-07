"""CP15: URL routes for the communications API, mounted at
/api/v1/communications/ by config/urls.py.

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

Built entirely from DRF's ``DefaultRouter``.
"""
from rest_framework.routers import DefaultRouter

from .views import CommunicationLogViewSet, EmailMessageViewSet, EmailTemplateViewSet, NotificationViewSet

app_name = "communications"

router = DefaultRouter()
router.register("email-templates", EmailTemplateViewSet, basename="email-template")
router.register("email-messages", EmailMessageViewSet, basename="email-message")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("communication-logs", CommunicationLogViewSet, basename="communication-log")

urlpatterns = router.urls
