"""CP16: tests for apps/reports/models.py."""
import pytest

from apps.reports.models import Dashboard, DashboardWidget, ReportExecution, SavedReport

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_saved_report_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in SavedReport._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_saved_report_str_returns_name():
    assert str(SavedReport(name="Weekly Productivity")) == "Weekly Productivity"


def test_saved_report_filters_defaults_to_empty_dict():
    assert SavedReport._meta.get_field("filters").default() == {}


def test_saved_report_is_active_defaults_true_and_distinct_from_is_deleted():
    assert SavedReport._meta.get_field("is_active").default is True
    assert SavedReport._meta.get_field("is_deleted").default is False


def test_report_execution_owner_property_delegates_to_report_owner():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="owner@example.com")
    report = SavedReport(name="R", owner=user)
    execution = ReportExecution(report=report)
    assert execution.owner is user


def test_report_execution_status_defaults_to_pending():
    assert ReportExecution._meta.get_field("status").default == ReportExecution.Status.PENDING


def test_dashboard_str_returns_name():
    assert str(Dashboard(name="Sales Overview")) == "Sales Overview"


def test_dashboard_has_unique_default_constraint():
    constraint_names = {c.name for c in Dashboard._meta.constraints}
    assert "reports_dashboard_unique_default_per_owner" in constraint_names


def test_dashboard_widget_owner_property_delegates_to_dashboard_owner():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="owner2@example.com")
    dashboard = Dashboard(name="D", owner=user)
    widget = DashboardWidget(dashboard=dashboard)
    assert widget.owner is user


def test_dashboard_widget_str_includes_dashboard_and_title():
    dashboard = Dashboard(name="Sales")
    widget = DashboardWidget(dashboard=dashboard, title="Pipeline Funnel")
    assert "Sales" in str(widget)
    assert "Pipeline Funnel" in str(widget)


def test_dashboard_widget_position_defaults_to_zero():
    assert DashboardWidget._meta.get_field("position").default == 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_saved_report_create_and_retrieve(employee):
    report = SavedReport.objects.create(
        name="Pipeline", report_type=SavedReport.ReportType.SALES_PIPELINE, owner=employee
    )
    assert SavedReport.objects.get(pk=report.pk).is_active is True


@pytest.mark.django_db
def test_deleting_saved_report_cascades_to_executions(saved_report):
    execution = ReportExecution.objects.create(report=saved_report)
    saved_report.delete()
    assert not ReportExecution.objects.filter(pk=execution.pk).exists()


@pytest.mark.django_db
def test_dashboard_default_uniqueness_enforced(employee):
    from django.db import IntegrityError

    Dashboard.objects.create(name="First", owner=employee, is_default=True)
    with pytest.raises(IntegrityError):
        Dashboard.objects.create(name="Second", owner=employee, is_default=True)


@pytest.mark.django_db
def test_dashboard_default_uniqueness_allows_two_non_default(employee):
    Dashboard.objects.create(name="First", owner=employee, is_default=False)
    Dashboard.objects.create(name="Second", owner=employee, is_default=False)  # must not raise


@pytest.mark.django_db
def test_dashboard_default_uniqueness_allows_different_owners_each_default(employee, other_employee):
    Dashboard.objects.create(name="First", owner=employee, is_default=True)
    Dashboard.objects.create(name="Second", owner=other_employee, is_default=True)  # must not raise


@pytest.mark.django_db
def test_deleting_dashboard_cascades_to_widgets(dashboard, saved_report):
    widget = DashboardWidget.objects.create(dashboard=dashboard, report=saved_report, title="W")
    dashboard.delete()
    assert not DashboardWidget.objects.filter(pk=widget.pk).exists()


@pytest.mark.django_db
def test_saved_report_manager_has_access_true_for_managed_owner(manager, employee, organization):
    from apps.organization.models import Department, Membership, Team

    department = Department.objects.create(organization=organization, name="Ops")
    team = Team.objects.create(department=department, name="Ops Team", manager=manager)
    Membership.objects.create(team=team, user=employee)

    report = SavedReport.objects.create(
        name="R", report_type=SavedReport.ReportType.PRODUCTIVITY, owner=employee
    )

    assert report.manager_has_access(manager) is True
