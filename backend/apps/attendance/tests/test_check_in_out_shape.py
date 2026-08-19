"""Staff-management pass: the Check In / Check Out response shape.

The attendance ledger itself is unchanged — these tests assert that the
daily summary cleanly exposes exactly what a Check-In/Check-Out-oriented
UI needs (check-in time, check-out time, gross hours, effective hours, and
a flat chronological list of clock events) and that the pre-existing field
names still work.
"""
import datetime

import pytest
from django.utils import timezone

from apps.attendance.services import (
    build_time_logs,
    compute_daily_summary,
    end_session,
    start_break,
    end_break,
    start_session,
)

DAILY_SUMMARY_URL = "/api/v1/attendance/sessions/daily-summary/"


@pytest.fixture
def worked_day(db, employee):
    """A realistic day: check in, work, take a break, resume, check out."""
    base = timezone.now() - datetime.timedelta(hours=4)
    session = start_session(employee, now=base)
    start_break(session, now=base + datetime.timedelta(hours=1))
    end_break(session, now=base + datetime.timedelta(hours=1, minutes=30))
    end_session(session, now=base + datetime.timedelta(hours=3))
    return session


def test_summary_exposes_check_in_and_check_out(employee, worked_day):
    summary = compute_daily_summary(employee, timezone.localdate())

    assert summary["check_in_time"] == summary["login_time"] == worked_day.login_at
    assert summary["check_out_time"] == summary["logout_time"] == worked_day.logout_at


def test_summary_exposes_gross_and_effective_seconds(employee, worked_day):
    summary = compute_daily_summary(employee, timezone.localdate())

    # Aliases over the existing, unchanged totals — never a second calculation.
    assert summary["gross_seconds"] == summary["session_seconds"]
    assert summary["effective_seconds"] == summary["active_working_seconds"]
    # A 30-minute break means effective < gross.
    assert summary["effective_seconds"] < summary["gross_seconds"]


def test_summary_exposes_shift_and_role(employee, worked_day):
    summary = compute_daily_summary(employee, timezone.localdate())

    assert summary["employee_role"] == employee.role
    assert "shift_start_time" in summary
    assert "shift_end_time" in summary


def test_time_logs_are_chronological_and_typed(employee, worked_day):
    summary = compute_daily_summary(employee, timezone.localdate())
    logs = summary["time_logs"]

    assert logs, "a worked day must produce at least a check-in and check-out"
    assert logs[0]["type"] == "CHECK_IN"
    assert logs[-1]["type"] == "CHECK_OUT"
    assert [entry["at"] for entry in logs] == sorted(entry["at"] for entry in logs)

    kinds = {entry["type"] for entry in logs}
    assert "BREAK_START" in kinds
    assert "BREAK_END" in kinds


def test_time_logs_are_deduplicated(employee, worked_day):
    logs = build_time_logs([worked_day])
    keys = [(entry["at"], entry["type"]) for entry in logs]

    assert len(keys) == len(set(keys))


def test_time_logs_are_empty_for_a_day_with_no_sessions(employee):
    assert build_time_logs([]) == []


def test_daily_summary_endpoint_returns_the_check_in_out_fields(api_client, employee, worked_day):
    api_client.force_authenticate(employee)

    response = api_client.get(DAILY_SUMMARY_URL)

    assert response.status_code == 200
    for field in (
        "check_in_time", "check_out_time", "gross_seconds", "effective_seconds",
        "shift_start_time", "shift_end_time", "time_logs", "employee_role",
    ):
        assert field in response.data
    # Original field names still present — nothing was renamed away.
    for field in ("login_time", "logout_time", "session_seconds", "active_working_seconds"):
        assert field in response.data


def test_no_record_day_still_returns_the_check_in_out_fields(api_client, employee):
    api_client.force_authenticate(employee)

    response = api_client.get(f"{DAILY_SUMMARY_URL}?date=2000-01-01")

    assert response.status_code == 200
    assert response.data["status"] == "No Record"
    assert response.data["check_in_time"] is None
    assert response.data["check_out_time"] is None
    assert response.data["time_logs"] == []


# --------------------------------------------------------------------------
# Visibility scoping (re-verified, not rebuilt)
# --------------------------------------------------------------------------


def test_employee_cannot_read_another_employees_summary(api_client, employee, other_employee, worked_day):
    api_client.force_authenticate(other_employee)

    response = api_client.get(f"{DAILY_SUMMARY_URL}?employee_id={employee.pk}")

    assert response.status_code == 404


def test_manager_can_read_their_own_team_members_summary(api_client, manager, employee, team, worked_day):
    api_client.force_authenticate(manager)

    response = api_client.get(f"{DAILY_SUMMARY_URL}?employee_id={employee.pk}")

    assert response.status_code == 200


def test_manager_cannot_read_an_out_of_scope_summary(api_client, manager, other_employee):
    api_client.force_authenticate(manager)

    response = api_client.get(f"{DAILY_SUMMARY_URL}?employee_id={other_employee.pk}")

    assert response.status_code == 404


def test_super_admin_can_read_anyones_summary(api_client, super_admin, employee, worked_day):
    api_client.force_authenticate(super_admin)

    response = api_client.get(f"{DAILY_SUMMARY_URL}?employee_id={employee.pk}")

    assert response.status_code == 200
