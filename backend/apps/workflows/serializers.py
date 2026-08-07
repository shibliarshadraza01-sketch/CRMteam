"""CP17: serializers for the workflow automation domain.

Every serializer mixes in CP7's `SoftDeleteTimeStampedSerializerMixin`.
`WorkflowExecution` reuses CP14's `RelatedObjectMixin`
(`apps.activities.serializers`) UNCHANGED for the same read-only
`related_object` summary shape CP15's `EmailMessage`/`Notification`
already reuse.
"""
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.activities.serializers import RelatedObjectMixin
from apps.core.serializers import SoftDeleteTimeStampedSerializerMixin

from .models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger


class _WorkflowsSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base: every workflows serializer gets the CP7 timestamp/
    audit/soft-delete field shape without repeating it per class.
    """


class WorkflowTriggerSerializer(_WorkflowsSerializer):
    class Meta:
        model = WorkflowTrigger
        fields = [
            "id", "workflow", "trigger_type", "content_type", "conditions",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class WorkflowActionSerializer(_WorkflowsSerializer):
    class Meta:
        model = WorkflowAction
        fields = [
            "id", "workflow", "action_type", "configuration", "position",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class WorkflowExecutionSerializer(RelatedObjectMixin, _WorkflowsSerializer):
    """Entirely read-only — see `models.py`'s `WorkflowExecution` docstring
    and `views.py`: there is no create endpoint, only list/retrieve
    (executions are created exclusively via `WorkflowViewSet.execute`).
    """

    class Meta:
        model = WorkflowExecution
        fields = [
            "id", "workflow", "trigger", "status", "started_at", "completed_at",
            "result_data", "error_message", "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = fields


class WorkflowSerializer(_WorkflowsSerializer):
    class Meta:
        model = Workflow
        fields = [
            "id", "name", "description", "owner", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class WorkflowDetailSerializer(WorkflowSerializer):
    """Read-only: nests this workflow's triggers and actions."""

    triggers = WorkflowTriggerSerializer(many=True, read_only=True)
    actions = WorkflowActionSerializer(many=True, read_only=True)

    class Meta(WorkflowSerializer.Meta):
        fields = WorkflowSerializer.Meta.fields + ["triggers", "actions"]
        read_only_fields = fields


class WorkflowExecuteSerializer(serializers.Serializer):
    """Write-only input shape for `WorkflowViewSet.execute()` — identifies
    which entity to run the workflow against.
    """

    content_type = serializers.PrimaryKeyRelatedField(queryset=ContentType.objects.all(), required=True)
    object_id = serializers.IntegerField(required=True)
