"""API-level tests for apps/attendance/views.py — focused on the
Employee/Manager/Super-Admin permission boundaries (Part 11/12) and the
end-to-end request/response shape of the state-machine actions.
"""
import pytest
from django.utils import timezone

from apps.attendance.services import start_session


def _auth(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
def test_start_heartbeat_break_end_flow(api_client, employee, shift_config):
    _auth(api_client, employee)

    resp = api_client.post("/api/v1/attendance/sessions/start/")
    assert resp.status_code == 201
    assert resp.data["display_state"] == "WORKING"

    resp = api_client.post("/api/v1/attendance/sessions/heartbeat/")
    assert resp.status_code == 200

    resp = api_client.post("/api/v1/attendance/sessions/break-start/")
    assert resp.status_code == 200
    assert resp.data["display_state"] == "ON_BREAK"

    resp = api_client.post("/api/v1/attendance/sessions/break-end/")
    assert resp.status_code == 200
    assert resp.data["display_state"] == "WORKING"

    resp = api_client.post("/api/v1/attendance/sessions/end/")
    assert resp.status_code == 200
    assert resp.data["display_state"] == "OFFLINE"

    # Idempotent: calling end again with no open session must not fail.
    resp = api_client.post("/api/v1/attendance/sessions/end/")
    assert resp.status_code == 200
    assert resp.data["session"] is None


@pytest.mark.django_db
def test_break_start_without_open_session_returns_404(api_client, employee):
    _auth(api_client, employee)
    resp = api_client.post("/api/v1/attendance/sessions/break-start/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_daily_summary_defaults_to_self(api_client, employee, shift_config):
    start_session(employee)
    _auth(api_client, employee)

    resp = api_client.get("/api/v1/attendance/sessions/daily-summary/")
    assert resp.status_code == 200
    assert resp.data["employee_id"] == employee.id


@pytest.mark.django_db
def test_daily_summary_employee_cannot_view_another_employee(api_client, employee, other_employee, shift_config):
    start_session(other_employee)
    _auth(api_client, employee)

    resp = api_client.get(f"/api/v1/attendance/sessions/daily-summary/?employee_id={other_employee.id}")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_daily_summary_manager_can_view_own_team_member(api_client, manager, employee, team, shift_config):
    start_session(employee)
    _auth(api_client, manager)

    resp = api_client.get(f"/api/v1/attendance/sessions/daily-summary/?employee_id={employee.id}")
    assert resp.status_code == 200
    assert resp.data["employee_id"] == employee.id


@pytest.mark.django_db
def test_daily_summary_manager_cannot_view_employee_outside_team(api_client, manager, other_employee, team, shift_config):
    start_session(other_employee)
    _auth(api_client, manager)

    resp = api_client.get(f"/api/v1/attendance/sessions/daily-summary/?employee_id={other_employee.id}")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_daily_summary_super_admin_can_view_anyone(api_client, super_admin, other_employee, shift_config):
    start_session(other_employee)
    _auth(api_client, super_admin)

    resp = api_client.get(f"/api/v1/attendance/sessions/daily-summary/?employee_id={other_employee.id}")
    assert resp.status_code == 200
    assert resp.data["employee_id"] == other_employee.id


@pytest.mark.django_db
def test_team_status_empty_for_plain_employee(api_client, employee):
    _auth(api_client, employee)
    resp = api_client.get("/api/v1/attendance/sessions/team-status/")
    assert resp.status_code == 200
    assert resp.data == []


@pytest.mark.django_db
def test_team_status_manager_sees_only_own_team(api_client, manager, employee, other_employee, team, shift_config):
    start_session(employee)
    start_session(other_employee)  # not on the manager's team
    _auth(api_client, manager)

    resp = api_client.get("/api/v1/attendance/sessions/team-status/")
    assert resp.status_code == 200
    seen_ids = {row["employee_id"] for row in resp.data}
    assert employee.id in seen_ids
    assert other_employee.id not in seen_ids


@pytest.mark.django_db
def test_company_report_forbidden_for_non_super_admin(api_client, manager):
    _auth(api_client, manager)
    resp = api_client.get("/api/v1/attendance/sessions/company-report/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_company_report_super_admin_sees_all(api_client, super_admin, employee, other_employee, shift_config):
    start_session(employee)
    start_session(other_employee)
    _auth(api_client, super_admin)

    resp = api_client.get("/api/v1/attendance/sessions/company-report/")
    assert resp.status_code == 200
    seen_ids = {row["employee_id"] for row in resp.data}
    assert employee.id in seen_ids
    assert other_employee.id in seen_ids


@pytest.mark.django_db
def test_company_report_rejects_range_over_31_days(api_client, super_admin):
    _auth(api_client, super_admin)
    today = timezone.localdate()
    date_from = (today.replace(day=1)).isoformat()
    resp = api_client.get(
        f"/api/v1/attendance/sessions/company-report/?date_from=2026-01-01&date_to=2026-03-15"
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_shift_config_current_auto_creates_default(api_client, employee):
    _auth(api_client, employee)
    resp = api_client.get("/api/v1/attendance/shift-config/current/")
    assert resp.status_code == 200
    assert resp.data["shift_duration_minutes"] == 540


@pytest.mark.django_db
def test_shift_config_write_forbidden_for_employee(api_client, employee):
    _auth(api_client, employee)
    resp = api_client.post(
        "/api/v1/attendance/shift-config/",
        {"shift_duration_minutes": 480},
        format="json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_shift_config_write_allowed_for_super_admin(api_client, super_admin):
    _auth(api_client, super_admin)
    resp = api_client.post(
        "/api/v1/attendance/shift-config/",
        {"shift_duration_minutes": 480},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["shift_duration_minutes"] == 480
