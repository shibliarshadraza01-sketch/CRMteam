"""CP14: serializers for the activity layer.

Every serializer mixes in CP7's ``SoftDeleteTimeStampedSerializerMixin``,
exactly like every CP9+ serializer. `content_type`/`object_id` stay plain
writable fields (a PK and an int — no different from any other FK-shaped
field), and each serializer additionally exposes a read-only
``related_object`` summary (via ``RelatedObjectMixin`` below) so a client
doesn't have to separately fetch the attached `Customer`/`Lead`/
`Opportunity`/`Quote`/`Invoice` just to show "what is this attached to" —
without fully nesting five different possible serializers, which would
require a serializer-per-content-type dispatch table this checkpoint's
scope doesn't call for.
"""
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.serializers import SoftDeleteTimeStampedSerializerMixin

from .models import ActivityLog, Event, Reminder, Task


class RelatedObjectMixin(serializers.Serializer):
    """Adds a read-only ``related_object`` summary — ``None`` when
    `content_type`/`object_id` aren't set, otherwise a small dict
    identifying what this row is attached to. Deliberately NOT a full
    nested serializer of the target model: the target could be any of five
    unrelated models, so a generic `{type, id, label}` summary is the
    simplest shape that avoids a content-type-keyed serializer dispatch
    table this checkpoint doesn't need.
    """

    related_object = serializers.SerializerMethodField()

    @extend_schema_field(
        {
            "type": "object",
            "nullable": True,
            "properties": {
                "type": {"type": "string"},
                "id": {"type": "integer"},
                "label": {"type": "string"},
            },
        }
    )
    def get_related_object(self, obj):
        if obj.content_type_id is None or obj.object_id is None:
            return None
        target = obj.related_object
        if target is None:
            return None
        return {
            "type": f"{obj.content_type.app_label}.{obj.content_type.model}",
            "id": obj.object_id,
            "label": str(target),
        }


class _ActivitiesSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base: every activities serializer gets the CP7 timestamp/
    audit/soft-delete field shape without repeating it per class.
    """


class TaskSerializer(RelatedObjectMixin, _ActivitiesSerializer):
    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "owner", "assigned_to", "priority", "status",
            "due_date", "completed_at", "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class EventSerializer(RelatedObjectMixin, _ActivitiesSerializer):
    is_recurring = serializers.BooleanField(read_only=True)

    class Meta:
        model = Event
        fields = [
            "id", "title", "description", "owner", "location", "start_at", "end_at",
            "recurrence_frequency", "recurrence_end_date", "is_recurring",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class ActivityLogSerializer(RelatedObjectMixin, _ActivitiesSerializer):
    class Meta:
        model = ActivityLog
        fields = [
            "id", "actor", "activity_type", "description", "occurred_at",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class ReminderSerializer(_ActivitiesSerializer):
    class Meta:
        model = Reminder
        fields = [
            "id", "task", "event", "remind_at", "message", "is_sent",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]

    def validate(self, attrs):
        """Mirrors the model's ``exactly_one_of_task_or_event`` check
        constraint with a friendlier 400 — same pattern as CP13's
        `PriceBookEntrySerializer`.
        """
        task = attrs.get("task", getattr(self.instance, "task", None))
        event = attrs.get("event", getattr(self.instance, "event", None))
        if (task is None) == (event is None):
            raise serializers.ValidationError(
                "Provide exactly one of `task` or `event`, not both and not neither."
            )
        return attrs


class ReminderDetailSerializer(ReminderSerializer):
    """Read-only: nests the task's/event's own title instead of a bare PK."""

    task_title = serializers.CharField(source="task.title", read_only=True, default=None)
    event_title = serializers.CharField(source="event.title", read_only=True, default=None)

    class Meta(ReminderSerializer.Meta):
        fields = ReminderSerializer.Meta.fields + ["task_title", "event_title"]
        read_only_fields = fields
