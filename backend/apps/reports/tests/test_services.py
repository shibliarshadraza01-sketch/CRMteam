"""CP16: tests for apps/reports/services.py."""
import pytest

from apps.reports.models import Dashboard, DashboardWidget, ReportExecution, SavedReport
from apps.reports.services import (
    add_widget,
    create_dashboard,
    create_saved_report,
    execute_report,
    managed_user_ids,
    scope_queryset_for_user,
    set_default_dashboard,
    update_widget_configuration,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_managed_user_ids_and_scope_queryset_for_user_are_reexported_from_crm():
    from apps.crm import services as crm_services

    assert managed_user_ids is crm_services.managed_user_ids
    assert scope_queryset_for_user is crm_services.scope_queryset_for_user


def test_every_report_type_has_a_registered_compute_function():
    from apps.reports.services import _REPORT_COMPUTERS

    for report_type in SavedReport.ReportType.values:
        assert report_type in _REPORT_COMPUTERS


def test_compute_custom_returns_empty_result_without_hitting_db():
    from apps.reports.services import _compute_custom

    assert _compute_custom({}) == {"rows": [], "summary": {}}


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_saved_report_basic(employee):
    report = create_saved_report("Weekly", SavedReport.ReportType.PRODUCTIVITY, owner=employee)
    assert report.owner_id == employee.id
    assert report.filters == {}


@pytest.mark.django_db
def test_execute_report_custom_completes_with_empty_result(saved_report):
    saved_report.report_type = SavedReport.ReportType.CUSTOM
    saved_report.save()

    execution = execute_report(saved_report)

    assert execution.status == ReportExecution.Status.COMPLETED
    assert execution.result_data == {"rows": [], "summary": {}}
    assert execution.row_count == 0
    assert execution.completed_at is not None


@pytest.mark.django_db
def test_execute_report_productivity_counts_completed_tasks(saved_report, employee):
    from apps.activities.models import Task

    Task.objects.create(title="Done", assigned_to=employee, status=Task.Status.COMPLETED)
    Task.objects.create(title="Not done", assigned_to=employee, status=Task.Status.PENDING)

    execution = execute_report(saved_report)

    assert execution.status == ReportExecution.Status.COMPLETED
    assert execution.result_data["summary"]["total_tasks_completed"] == 1
    row = execution.result_data["rows"][0]
    assert row["user_id"] == employee.id
    assert row["tasks_completed"] == 1


@pytest.mark.django_db
def test_execute_report_productivity_counts_activity_logs(saved_report, employee):
    from apps.activities.models import ActivityLog

    ActivityLog.objects.create(actor=employee, description="Called")
    ActivityLog.objects.create(actor=employee, description="Emailed")

    execution = execute_report(saved_report)

    assert execution.result_data["summary"]["total_activities_logged"] == 2


@pytest.mark.django_db
def test_execute_report_productivity_respects_owner_id_filter(employee, other_employee):
    from apps.activities.models import Task

    report = create_saved_report(
        "Filtered", SavedReport.ReportType.PRODUCTIVITY, filters={"owner_id": employee.id}
    )
    Task.objects.create(title="Mine", assigned_to=employee, status=Task.Status.COMPLETED)
    Task.objects.create(title="Not mine", assigned_to=other_employee, status=Task.Status.COMPLETED)

    execution = execute_report(report)

    assert execution.result_data["summary"]["total_tasks_completed"] == 1


@pytest.mark.django_db
def test_execute_report_lead_conversion_computes_rate(employee):
    from apps.crm.models import Customer, Lead

    report = create_saved_report("Conversion", SavedReport.ReportType.LEAD_CONVERSION)
    converted_lead = Lead.objects.create(company_name="A", contact_name="A", owner=employee)
    Lead.objects.create(company_name="B", contact_name="B", owner=employee)

    from apps.organization.models import Organization

    org = Organization.objects.create(name="Conv Org", slug="conv-org")
    customer = Customer.objects.create(organization=org, name="A", slug="a-customer", owner=employee)
    converted_lead.converted_customer = customer
    converted_lead.save()

    execution = execute_report(report)

    assert execution.result_data["summary"]["total_leads"] == 2
    assert execution.result_data["summary"]["converted_leads"] == 1
    assert execution.result_data["summary"]["conversion_rate_pct"] == 50.0


@pytest.mark.django_db
def test_execute_report_sales_pipeline_groups_by_stage(employee, organization):
    from apps.crm.models import Customer
    from apps.crm.opportunities import Opportunity

    report = create_saved_report("Pipeline", SavedReport.ReportType.SALES_PIPELINE)
    customer = Customer.objects.create(organization=organization, name="Pipeline Co", slug="pipeline-co", owner=employee)
    Opportunity.objects.create(customer=customer, title="Deal 1", owner=employee, stage=Opportunity.Stage.NEW, value=100)
    Opportunity.objects.create(customer=customer, title="Deal 2", owner=employee, stage=Opportunity.Stage.NEW, value=200)

    execution = execute_report(report)

    assert execution.result_data["summary"]["open_opportunity_count"] == 2
    row = execution.result_data["rows"][0]
    assert row["stage"] == Opportunity.Stage.NEW
    assert row["count"] == 2


@pytest.mark.django_db
def test_execute_report_customer_activity_groups_by_customer(employee, customer):
    from apps.activities.models import ActivityLog

    report = create_saved_report("Cust Activity", SavedReport.ReportType.CUSTOMER_ACTIVITY)
    from apps.activities.services import log_activity

    log_activity(customer, "CALL", "Called", actor=employee)
    log_activity(customer, "EMAIL", "Emailed", actor=employee)

    execution = execute_report(report)

    assert execution.result_data["summary"]["total_activities"] == 2
    assert execution.result_data["rows"][0]["customer_id"] == customer.pk
    assert execution.result_data["rows"][0]["activity_count"] == 2


@pytest.mark.django_db
def test_execute_report_failure_marks_execution_failed(saved_report, monkeypatch):
    from apps.reports import services

    def broken_compute(filters):
        raise RuntimeError("boom")

    monkeypatch.setitem(services._REPORT_COMPUTERS, SavedReport.ReportType.PRODUCTIVITY, broken_compute)

    execution = execute_report(saved_report)

    assert execution.status == ReportExecution.Status.FAILED
    assert execution.error_message == "boom"


@pytest.mark.django_db
def test_create_dashboard_demotes_existing_default(employee):
    first = create_dashboard("First", owner=employee, is_default=True)
    second = create_dashboard("Second", owner=employee, is_default=True)

    first.refresh_from_db()
    assert first.is_default is False
    assert second.is_default is True


@pytest.mark.django_db
def test_set_default_dashboard_demotes_previous(employee, dashboard):
    other = Dashboard.objects.create(name="Other", owner=employee, is_default=True)

    set_default_dashboard(dashboard)

    other.refresh_from_db()
    dashboard.refresh_from_db()
    assert other.is_default is False
    assert dashboard.is_default is True


@pytest.mark.django_db
def test_add_widget_auto_assigns_position(dashboard, saved_report):
    first = add_widget(dashboard, saved_report, DashboardWidget.WidgetType.TABLE, "First")
    second = add_widget(dashboard, saved_report, DashboardWidget.WidgetType.TABLE, "Second")

    assert first.position == 0
    assert second.position == 1


@pytest.mark.django_db
def test_add_widget_respects_explicit_position(dashboard, saved_report):
    widget = add_widget(dashboard, saved_report, DashboardWidget.WidgetType.CHART, "W", position=5)
    assert widget.position == 5


@pytest.mark.django_db
def test_update_widget_configuration_replaces_config(dashboard, saved_report):
    widget = add_widget(dashboard, saved_report, DashboardWidget.WidgetType.METRIC, "M")
    update_widget_configuration(widget, {"color": "blue"})
    widget.refresh_from_db()
    assert widget.configuration == {"color": "blue"}
