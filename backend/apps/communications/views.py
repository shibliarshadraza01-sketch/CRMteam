"""CP15: the communications domain's REST API.

Two viewset bases, matching the two access shapes `permissions.py`
documents:

- `_ReferenceDataModelViewSet` (`EmailTemplate` only) — no ownership
  scoping. Its shared no-PUT/active-vs-unfiltered shape now lives in
  `apps.core.views.ReferenceDataModelViewSetMixin` (factored out at CP20
  after the third independent occurrence of it — see that mixin's own
  docstring); only `permission_classes` is declared here, since
  `EmailTemplateWritePermission` is this app's own composition, not
  something `apps.catalog`'s or `apps.system`'s equivalent viewsets have
  any business depending on.
- CP10's `_CrmModelViewSet` (`apps.crm.views`), reused directly for
  `EmailMessage`/`Notification`/`CommunicationLog` — all three have a real
  or delegating `owner`, the same cross-app reuse CP12/CP14 already
  established.
"""
from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.utils import stamp_audit_fields
from apps.core.views import ReferenceDataModelViewSetMixin
from apps.crm.views import _CrmModelViewSet

from .filters import (
    CommunicationLogFilterSet,
    EmailMessageFilterSet,
    EmailTemplateFilterSet,
    NotificationFilterSet,
)
from .models import CommunicationLog, EmailMessage, EmailTemplate, Notification
from .permissions import EmailTemplateWritePermission
from .serializers import (
    CommunicationLogSerializer,
    EmailMessageQueueSerializer,
    EmailMessageSerializer,
    EmailTemplateSerializer,
    NotificationSerializer,
)
from .services import create_notification, mark_notification_read, mark_notification_unread, queue_email, send_queued_email


class _ReferenceDataModelViewSet(ReferenceDataModelViewSetMixin, viewsets.ModelViewSet):
    """Shared reference-data base — see this module's own docstring."""

    permission_classes = [IsAuthenticated, EmailTemplateWritePermission]


class EmailTemplateViewSet(_ReferenceDataModelViewSet):
    base_manager = EmailTemplate.objects
    base_active_manager = EmailTemplate.active_objects
    serializer_class = EmailTemplateSerializer
    filterset_class = EmailTemplateFilterSet
    search_fields = ["name", "subject"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]


class EmailMessageViewSet(_CrmModelViewSet):
    """`create()` is overridden entirely (not just `perform_create()`):
    queueing an email accepts a `template`(+`context`) OR `subject`+`body`
    input union (`EmailMessageQueueSerializer`) that doesn't map onto
    `EmailMessage`'s own flat field list the way ordinary creation does —
    see that serializer's docstring.
    """

    base_manager = EmailMessage.objects
    base_active_manager = EmailMessage.active_objects
    serializer_class = EmailMessageSerializer
    filterset_class = EmailMessageFilterSet
    search_fields = ["subject", "to_email"]
    ordering_fields = ["created_at", "sent_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("owner", "template", "content_type")

    @extend_schema(request=EmailMessageQueueSerializer, responses={201: EmailMessageSerializer})
    def create(self, request, *args, **kwargs):
        input_serializer = EmailMessageQueueSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        related_object = None
        content_type = data.get("content_type")
        object_id = data.get("object_id")
        if content_type is not None and object_id is not None:
            related_object = content_type.get_object_for_this_type(pk=object_id)

        message = queue_email(
            data["to_email"],
            template=data.get("template"),
            context=data.get("context"),
            subject=data.get("subject"),
            body=data.get("body"),
            owner=request.user,
            related_object=related_object,
        )
        stamp_audit_fields(message, request.user, creating=True)
        message.save()

        output_serializer = self.get_serializer(message)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: EmailMessageSerializer})
    @action(detail=True, methods=["post"])
    def send(self, request, *args, **kwargs):
        """``POST /email-messages/<id>/send/`` — attempts delivery
        (``services.send_queued_email()``); rejects an already-sent message.
        """
        message = self.get_object()
        try:
            send_queued_email(message)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(message)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationViewSet(_CrmModelViewSet):
    base_manager = Notification.objects
    base_active_manager = Notification.active_objects
    serializer_class = NotificationSerializer
    filterset_class = NotificationFilterSet
    owner_field = "recipient"
    search_fields = ["title", "message"]
    ordering_fields = ["created_at", "is_read"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("recipient", "content_type")

    def perform_create(self, serializer):
        """Routes creation through ``services.create_notification()`` —
        real behavior: automatically writes a ``CommunicationLog`` entry
        (this checkpoint's "communication logging" requirement), which a
        bare ``serializer.save()`` would skip.
        """
        data = dict(serializer.validated_data)
        recipient = data.pop("recipient")
        notification_type = data.pop("notification_type")
        title = data.pop("title")
        message = data.pop("message", "")
        related_object = None
        content_type = data.pop("content_type", None)
        object_id = data.pop("object_id", None)
        if content_type is not None and object_id is not None:
            related_object = content_type.get_object_for_this_type(pk=object_id)

        notification = create_notification(
            recipient, notification_type, title, message=message, related_object=related_object
        )
        stamp_audit_fields(notification, self.request.user, creating=True)
        notification.save()
        serializer.instance = notification

    @extend_schema(request=None, responses={200: NotificationSerializer})
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, *args, **kwargs):
        notification = self.get_object()
        mark_notification_read(notification)
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: NotificationSerializer})
    @action(detail=True, methods=["post"], url_path="mark-unread")
    def mark_unread(self, request, *args, **kwargs):
        notification = self.get_object()
        mark_notification_unread(notification)
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CommunicationLogViewSet(_CrmModelViewSet):
    """Read-only — ``http_method_names`` excludes every write verb, so
    there is no create/update/delete/restore/hard-delete route at all
    (DRF returns 405 for any of them), matching this model's own
    "written automatically by services, never by a client" design (see
    ``models.py``'s `CommunicationLog` docstring).
    """

    base_manager = CommunicationLog.objects
    base_active_manager = CommunicationLog.active_objects
    serializer_class = CommunicationLogSerializer
    filterset_class = CommunicationLogFilterSet
    owner_field = "actor"
    http_method_names = ["get", "head", "options"]
    search_fields = ["summary"]
    ordering_fields = ["occurred_at"]
    ordering = ["-occurred_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("actor", "content_type")
