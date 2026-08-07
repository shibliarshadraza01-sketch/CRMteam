"""CP16: tests for the querysets on apps/reports/models.py."""
import pytest

from apps.reports.models import Dashboard, DashboardWidget, ReportExecution, SavedReport

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_saved_report_active_filters_is_deleted_and_is_active_without_hitting_db():
    where_sql = str(SavedReport.objects.active().query.where)
    assert "is_deleted" in where_sql
    assert "is_active" in where_sql


def test_saved_report_by_owner_builds_filter_without_hitting_db():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert len(SavedReport.objects.by_owner(User(pk=1)).query.where) > 0


def test_dashboard_by_owner_builds_filter_without_hitting_db():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert len(Dashboard.objects.by_owner(User(pk=1)).query.where) > 0


def test_report_execution_for_report_builds_filter_without_hitting_db():
    report = SavedReport(pk=1, name="R", report_type=SavedReport.ReportType.CUSTOM)
    assert len(ReportExecution.objects.for_report(report).query.where) > 0


def test_dashboard_widget_for_dashboard_builds_filter_without_hitting_db():
    dashboard = Dashboard(pk=1, name="D")
    assert len(DashboardWidget.objects.for_dashboard(dashboard).query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_active_saved_report_manager_excludes_inactive_and_deleted(employee):
    active = SavedReport.objects.create(
        name="Active", report_type=SavedReport.ReportType.CUSTOM, owner=employee, is_active=True
    )
    SavedReport.objects.create(
        name="Inactive", report_type=SavedReport.ReportType.CUSTOM, owner=employee, is_active=False
    )
    deleted = SavedReport.objects.create(
        name="Deleted", report_type=SavedReport.ReportType.CUSTOM, owner=employee
    )
    deleted.soft_delete()

    names = set(SavedReport.active_objects.values_list("name", flat=True))
    assert names == {"Active"}


@pytest.mark.django_db
def test_report_execution_latest_for_report_returns_most_recent(saved_report):
    first = ReportExecution.objects.create(report=saved_report)
    second = ReportExecution.objects.create(report=saved_report)

    assert ReportExecution.objects.latest_for_report(saved_report) == second


@pytest.mark.django_db
def test_dashboard_widget_for_dashboard_matches_real_rows(dashboard, saved_report):
    matching = DashboardWidget.objects.create(dashboard=dashboard, report=saved_report, title="W1")
    other_dashboard = Dashboard.objects.create(name="Other")
    DashboardWidget.objects.create(dashboard=other_dashboard, report=saved_report, title="W2")

    assert list(DashboardWidget.objects.for_dashboard(dashboard)) == [matching]
