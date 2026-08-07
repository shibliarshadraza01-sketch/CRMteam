"""CP16: serializers for the reporting/dashboard domain.

Every serializer mixes in CP7's `SoftDeleteTimeStampedSerializerMixin`.
"""
from rest_framework import serializers

from apps.core.serializers import SoftDeleteTimeStampedSerializerMixin

from .models import Dashboard, DashboardWidget, ReportExecution, SavedReport


class _ReportsSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base: every reports serializer gets the CP7 timestamp/audit/
    soft-delete field shape without repeating it per class.
    """


class SavedReportSerializer(_ReportsSerializer):
    class Meta:
        model = SavedReport
        fields = [
            "id", "name", "description", "report_type", "owner", "filters", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class ReportExecutionSerializer(_ReportsSerializer):
    """Entirely read-only — see `models.py`'s `ReportExecution` docstring
    and `views.py`: there is no create endpoint, only list/retrieve
    (executions are created exclusively via `SavedReportViewSet.execute`).
    """

    class Meta:
        model = ReportExecution
        fields = [
            "id", "report", "executed_by", "status", "started_at", "completed_at",
            "result_data", "row_count", "error_message",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = fields


class DashboardSerializer(_ReportsSerializer):
    class Meta:
        model = Dashboard
        fields = [
            "id", "name", "owner", "is_default",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = ["is_default"]


class DashboardWidgetSerializer(_ReportsSerializer):
    class Meta:
        model = DashboardWidget
        fields = [
            "id", "dashboard", "report", "widget_type", "title", "position", "configuration",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class DashboardDetailSerializer(DashboardSerializer):
    """Read-only: nests this dashboard's widgets."""

    widgets = DashboardWidgetSerializer(many=True, read_only=True)

    class Meta(DashboardSerializer.Meta):
        fields = DashboardSerializer.Meta.fields + ["widgets"]
        read_only_fields = fields
