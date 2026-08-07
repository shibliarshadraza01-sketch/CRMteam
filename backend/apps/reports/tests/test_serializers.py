"""CP16: tests for apps/reports/serializers.py."""
import pytest
from rest_framework import serializers

from apps.reports.serializers import (
    DashboardDetailSerializer,
    DashboardSerializer,
    DashboardWidgetSerializer,
    ReportExecutionSerializer,
    SavedReportSerializer,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_saved_report_serializer_fields():
    fields = SavedReportSerializer().fields
    assert {
        "id", "name", "description", "report_type", "owner", "filters", "is_active",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_report_execution_serializer_is_entirely_read_only():
    for name, field in ReportExecutionSerializer().fields.items():
        assert field.read_only is True


def test_dashboard_serializer_is_default_is_read_only():
    fields = DashboardSerializer().fields
    assert fields["is_default"].read_only is True


def test_dashboard_widget_serializer_business_fields_writable():
    fields = DashboardWidgetSerializer().fields
    for name in ("dashboard", "report", "widget_type", "title", "position", "configuration"):
        assert fields[name].read_only is False


def test_dashboard_detail_serializer_nests_widgets():
    fields = DashboardDetailSerializer().fields
    assert isinstance(fields["widgets"], serializers.ListSerializer)


def test_dashboard_detail_serializer_is_entirely_read_only():
    for name, field in DashboardDetailSerializer().fields.items():
        assert field.read_only is True


# --------------------------------------------------------------------------
# Requires database — full serializer validation (FK fields query the DB)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_saved_report_serializer_full_validation(employee):
    serializer = SavedReportSerializer(data={"name": "R", "report_type": "CUSTOM", "owner": employee.pk})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_dashboard_widget_serializer_full_validation(dashboard, saved_report):
    serializer = DashboardWidgetSerializer(
        data={"dashboard": dashboard.pk, "report": saved_report.pk, "widget_type": "TABLE", "title": "W"}
    )
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_dashboard_detail_serializer_output(dashboard, saved_report):
    from apps.reports.services import add_widget

    add_widget(dashboard, saved_report, "TABLE", "W")
    data = DashboardDetailSerializer(dashboard).data

    assert len(data["widgets"]) == 1
    assert data["widgets"][0]["title"] == "W"
