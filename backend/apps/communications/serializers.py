"""CP15: serializers for the communications domain.

Every serializer mixes in CP7's `SoftDeleteTimeStampedSerializerMixin`.
`EmailMessage`/`Notification` reuse CP14's `RelatedObjectMixin`
(`apps.activities.serializers`) UNCHANGED for the same read-only
`related_object` summary shape `Task`/`Event`/`ActivityLog` already
expose — imported, not re-implemented.
"""
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.activities.serializers import RelatedObjectMixin
from apps.core.serializers import SoftDeleteTimeStampedSerializerMixin

from .models import CommunicationLog, EmailMessage, EmailTemplate, Notification


class _CommunicationsSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base: every communications serializer gets the CP7
    timestamp/audit/soft-delete field shape without repeating it per class.
    """


class EmailTemplateSerializer(_CommunicationsSerializer):
    class Meta:
        model = EmailTemplate
        fields = [
            "id", "name", "subject", "body", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class EmailMessageSerializer(RelatedObjectMixin, _CommunicationsSerializer):
    class Meta:
        model = EmailMessage
        fields = [
            "id", "template", "owner", "to_email", "subject", "body", "status", "sent_at", "error_message",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = ["subject", "body", "status", "sent_at", "error_message"]


class EmailMessageQueueSerializer(serializers.Serializer):
    """Write-only input shape for `EmailMessageViewSet.create()` — NOT a
    `ModelSerializer`: queueing an email is `services.queue_email()`'s
    "either a template+context, or an explicit subject+body" union, which
    doesn't map onto a single flat set of model fields the way ordinary
    creation does (see `views.py`'s `perform_create()`).
    """

    to_email = serializers.EmailField()
    template = serializers.PrimaryKeyRelatedField(queryset=EmailTemplate.active_objects.all(), required=False)
    context = serializers.DictField(required=False)
    subject = serializers.CharField(required=False, allow_blank=False)
    body = serializers.CharField(required=False, allow_blank=False)
    content_type = serializers.PrimaryKeyRelatedField(queryset=ContentType.objects.all(), required=False)
    object_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        """Mirrors `services.queue_email()`'s own "template XOR subject+body"
        rule with a friendlier 400 — same three-layer pattern (service +
        serializer) CP13/CP14 established, minus the DB constraint layer
        (queueing has no DB-enforceable invariant to mirror here, unlike
        `PriceBookEntry`/`Reminder`'s exactly-one-of constraints).
        """
        has_template = bool(attrs.get("template"))
        has_subject_and_body = bool(attrs.get("subject")) and bool(attrs.get("body"))
        if has_template == has_subject_and_body:
            raise serializers.ValidationError(
                "Provide either `template` (+ optional `context`), or both `subject` and `body`, not both forms."
            )
        return attrs


class NotificationSerializer(RelatedObjectMixin, _CommunicationsSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "recipient", "notification_type", "title", "message", "is_read", "read_at",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = ["is_read", "read_at"]


class CommunicationLogSerializer(RelatedObjectMixin, _CommunicationsSerializer):
    """Entirely read-only — see `models.py`'s `CommunicationLog` docstring
    and `views.py`: there is no create endpoint, only list/retrieve.
    """

    class Meta:
        model = CommunicationLog
        fields = [
            "id", "channel", "actor", "summary", "occurred_at",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = fields
