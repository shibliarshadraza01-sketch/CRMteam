"""CP16: tests for apps/reports/filters.py."""
import pytest

from apps.reports.filters import DashboardWidgetFilterSet, SavedReportFilterSet
from apps.reports.models import DashboardWidget, SavedReport

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_saved_report_filterset_declares_expected_fields():
    assert set(SavedReportFilterSet.Meta.fields) == {"report_type", "owner", "is_active"}


def test_dashboard_widget_filterset_declares_expected_fields():
    assert set(DashboardWidgetFilterSet.Meta.fields) == {"dashboard", "report", "widget_type"}


def test_report_type_filter_builds_query_without_hitting_db():
    filterset = SavedReportFilterSet(data={"report_type": "CUSTOM"}, queryset=SavedReport.objects.all())
    assert filterset.is_valid()
    assert len(filterset.qs.query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_report_type_filter_matches_real_rows(employee):
    matching = SavedReport.objects.create(
        name="Match", report_type=SavedReport.ReportType.CUSTOM, owner=employee
    )
    SavedReport.objects.create(
        name="No match", report_type=SavedReport.ReportType.PRODUCTIVITY, owner=employee
    )

    filterset = SavedReportFilterSet(data={"report_type": "CUSTOM"}, queryset=SavedReport.objects.all())

    assert list(filterset.qs) == [matching]


@pytest.mark.django_db
def test_widget_type_filter_matches_real_rows(dashboard, saved_report):
    matching = DashboardWidget.objects.create(
        dashboard=dashboard, report=saved_report, widget_type=DashboardWidget.WidgetType.CHART, title="C"
    )
    DashboardWidget.objects.create(
        dashboard=dashboard, report=saved_report, widget_type=DashboardWidget.WidgetType.TABLE, title="T"
    )

    filterset = DashboardWidgetFilterSet(data={"widget_type": "CHART"}, queryset=DashboardWidget.objects.all())

    assert list(filterset.qs) == [matching]
