"""CP16: end-to-end tests for the reports API. Requires a real database."""
import pytest

from apps.reports.models import Dashboard, ReportExecution, SavedReport

pytestmark = pytest.mark.django_db

SAVED_REPORTS_URL = "/api/v1/reports/saved-reports/"
REPORT_EXECUTIONS_URL = "/api/v1/reports/report-executions/"
DASHBOARDS_URL = "/api/v1/reports/dashboards/"
DASHBOARD_WIDGETS_URL = "/api/v1/reports/dashboard-widgets/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# SavedReport CRUD + ownership scoping
# --------------------------------------------------------------------------


def test_unauthenticated_denied(api_client):
    response = api_client.get(SAVED_REPORTS_URL)
    assert response.status_code == 401


def test_employee_can_create_and_owns_it_by_default(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(SAVED_REPORTS_URL, {"name": "My Report", "report_type": "CUSTOM"})
    assert response.status_code == 201
    assert response.data["owner"] == employee.id


def test_employee_cannot_see_another_employees_report(api_client, employee, other_employee):
    SavedReport.objects.create(name="Not mine", report_type=SavedReport.ReportType.CUSTOM, owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(SAVED_REPORTS_URL)

    assert response.data["count"] == 0


def test_super_admin_sees_every_report(api_client, super_admin, saved_report):
    api_client.force_authenticate(super_admin)
    response = api_client.get(SAVED_REPORTS_URL)
    assert response.data["count"] == 1


def test_put_not_allowed(api_client, employee, saved_report):
    api_client.force_authenticate(employee)
    response = api_client.put(_detail(SAVED_REPORTS_URL, saved_report.pk), {"name": "X"})
    assert response.status_code == 405


def test_delete_soft_deletes(api_client, employee, saved_report):
    api_client.force_authenticate(employee)
    response = api_client.delete(_detail(SAVED_REPORTS_URL, saved_report.pk))
    assert response.status_code == 204
    saved_report.refresh_from_db()
    assert saved_report.is_deleted is True


# --------------------------------------------------------------------------
# execute action + ReportExecution read-only endpoint
# --------------------------------------------------------------------------


def test_execute_action_creates_completed_execution(api_client, employee, saved_report):
    api_client.force_authenticate(employee)
    response = api_client.post(f"{_detail(SAVED_REPORTS_URL, saved_report.pk)}execute/")
    assert response.status_code == 201
    assert response.data["status"] == "COMPLETED"
    assert ReportExecution.objects.filter(report=saved_report).exists()


def test_report_execution_has_no_create_endpoint(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(REPORT_EXECUTIONS_URL, {"report": 1})
    assert response.status_code == 405


def test_employee_sees_only_executions_of_their_own_reports(api_client, employee, other_employee):
    from apps.reports.services import create_saved_report, execute_report

    mine = create_saved_report("Mine", SavedReport.ReportType.CUSTOM, owner=employee)
    theirs = create_saved_report("Theirs", SavedReport.ReportType.CUSTOM, owner=other_employee)
    execute_report(mine)
    execute_report(theirs)
    api_client.force_authenticate(employee)

    response = api_client.get(REPORT_EXECUTIONS_URL)

    assert response.data["count"] == 1


# --------------------------------------------------------------------------
# Dashboard CRUD + set-default action
# --------------------------------------------------------------------------


def test_employee_can_create_dashboard(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(DASHBOARDS_URL, {"name": "My Dashboard"})
    assert response.status_code == 201
    assert response.data["is_default"] is False


def test_is_default_cannot_be_set_via_plain_create(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(DASHBOARDS_URL, {"name": "D", "is_default": True})
    assert response.status_code == 201
    assert response.data["is_default"] is False  # read-only field, ignored


def test_set_default_action_promotes_and_demotes(api_client, employee, dashboard):
    other = Dashboard.objects.create(name="Other", owner=employee, is_default=True)
    api_client.force_authenticate(employee)

    response = api_client.post(f"{_detail(DASHBOARDS_URL, dashboard.pk)}set-default/")

    assert response.status_code == 200
    assert response.data["is_default"] is True
    other.refresh_from_db()
    assert other.is_default is False


def test_retrieve_dashboard_uses_detail_serializer(api_client, employee, dashboard, saved_report):
    from apps.reports.services import add_widget

    add_widget(dashboard, saved_report, "TABLE", "W")
    api_client.force_authenticate(employee)

    response = api_client.get(_detail(DASHBOARDS_URL, dashboard.pk))

    assert response.status_code == 200
    assert "widgets" in response.data
    assert len(response.data["widgets"]) == 1


# --------------------------------------------------------------------------
# DashboardWidget CRUD + auto-position
# --------------------------------------------------------------------------


def test_create_widget_auto_assigns_position(api_client, employee, dashboard, saved_report):
    api_client.force_authenticate(employee)
    first = api_client.post(
        DASHBOARD_WIDGETS_URL, {"dashboard": dashboard.pk, "report": saved_report.pk, "widget_type": "TABLE", "title": "First"}
    )
    second = api_client.post(
        DASHBOARD_WIDGETS_URL, {"dashboard": dashboard.pk, "report": saved_report.pk, "widget_type": "TABLE", "title": "Second"}
    )
    assert first.data["position"] == 0
    assert second.data["position"] == 1


def test_employee_cannot_see_widget_on_someone_elses_dashboard(api_client, employee, other_employee, saved_report):
    other_dashboard = Dashboard.objects.create(name="Theirs", owner=other_employee)
    from apps.reports.services import add_widget

    add_widget(other_dashboard, saved_report, "TABLE", "W")
    api_client.force_authenticate(employee)

    response = api_client.get(DASHBOARD_WIDGETS_URL)

    assert response.data["count"] == 0


# --------------------------------------------------------------------------
# Search / filter / ordering / pagination
# --------------------------------------------------------------------------


def test_search_saved_reports_by_name(api_client, employee):
    SavedReport.objects.create(name="Quarterly Sales", report_type=SavedReport.ReportType.CUSTOM, owner=employee)
    SavedReport.objects.create(name="Other", report_type=SavedReport.ReportType.CUSTOM, owner=employee)

    api_client.force_authenticate(employee)
    response = api_client.get(SAVED_REPORTS_URL, {"search": "Quarterly"})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Quarterly Sales"}


def test_pagination_default_page_size_is_20(api_client, employee):
    for i in range(25):
        SavedReport.objects.create(name=f"Report {i:03d}", report_type=SavedReport.ReportType.CUSTOM, owner=employee)
    api_client.force_authenticate(employee)

    response = api_client.get(SAVED_REPORTS_URL)

    assert len(response.data["results"]) == 20
    assert response.data["count"] == 25
