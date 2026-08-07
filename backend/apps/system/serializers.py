"""CP19: serializers for the system/platform domain.

`AuditLog` reuses CP14's `RelatedObjectMixin` (`apps.activities
.serializers`) UNCHANGED for the same read-only `related_object` summary
shape CP15's `EmailMessage`/`Notification` and CP17's `WorkflowExecution`
already reuse.
"""
from rest_framework import serializers

from apps.activities.serializers import RelatedObjectMixin
from apps.core.serializers import TimeStampedSerializerMixin, SoftDeleteTimeStampedSerializerMixin

from .models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting


class AuditLogSerializer(RelatedObjectMixin, TimeStampedSerializerMixin, serializers.ModelSerializer):
    """Entirely read-only — see `models.py`'s `AuditLog` docstring and
    `views.py`: there is no create/update/delete endpoint of ANY kind,
    not even soft-delete (only `TimeStampedSerializerMixin` is mixed in
    here, not `SoftDeleteTimeStampedSerializerMixin` — `AuditLog` has no
    `is_deleted`/`deleted_at` fields to expose, matching its model's own
    deliberate lack of soft-delete support).
    """

    class Meta:
        model = AuditLog
        fields = [
            "id", "actor", "action", "description", "changes", "ip_address",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by",
        ]
        read_only_fields = fields


class _SystemSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base for the three ordinary soft-deletable models in this
    app — every field shape CP7 established, without repeating it per
    class.
    """


class SystemSettingSerializer(_SystemSerializer):
    class Meta:
        model = SystemSetting
        fields = [
            "id", "key", "value", "description", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class FeatureFlagSerializer(_SystemSerializer):
    class Meta:
        model = FeatureFlag
        fields = [
            "id", "key", "name", "description", "is_enabled", "rollout_percentage",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]

    def validate_rollout_percentage(self, value):
        if not 0 <= value <= 100:
            raise serializers.ValidationError("rollout_percentage must be between 0 and 100.")
        return value


class BackgroundJobSerializer(_SystemSerializer):
    """Business fields beyond `name`/`job_type`/`owner` are read-only —
    a `BackgroundJob`'s status lifecycle is entirely managed by
    `services.py` (`start_background_job()`/`complete_background_job()`/
    `fail_background_job()`), never by a direct PATCH, the same
    "state-machine fields are read-only, actions are the only way
    through" pattern CP11's `Opportunity.stage` established.
    """

    class Meta:
        model = BackgroundJob
        fields = [
            "id", "name", "job_type", "owner", "status", "started_at", "completed_at",
            "result_data", "error_message",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = ["status", "started_at", "completed_at", "result_data", "error_message"]
