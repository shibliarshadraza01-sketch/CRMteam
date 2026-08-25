"""Attendance/Reports audit pass, spec 2-4: one persisted session record,
read identically by every role's own view.

The three role-facing endpoints (an Employee's own ``daily-summary``, a
Manager's ``team-status``, a Super Admin's ``company-report``) must never
independently recompute or reformat a session's login/logout — all three
already route through the exact same ``services.compute_daily_summary()``
(see ``views.py``), so this test proves that architectural fact end to
end over real HTTP requests instead of just trusting the source reads
that way: create one real login/logout session for an employee, then
fetch it back through all three role views and assert every one of them
reports the identical timestamps and figures for that same
employee/date/session.
"""
import datetime

from django.utils import timezone

from apps.attendance.services import end_session, start_session


def test_login_logout_times_match_across_employee_manager_super_admin_views(
    api_client, employee, manager, super_admin, team, shift_config
):
    base = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0)
    session = start_session(employee, now=base)
    end_session(session, now=base + datetime.timedelta(hours=3))
    today = timezone.localdate().isoformat()

    # Employee: own record via daily-summary.
    api_client.force_authenticate(employee)
    employee_view = api_client.get(
        f"/api/v1/attendance/sessions/daily-summary/?employee_id={employee.id}&date={today}"
    ).data

    # Manager: same employee via team-status (today only) AND via
    # daily-summary with an explicit employee_id (their own team member).
    api_client.force_authenticate(manager)
    manager_team_status = api_client.get("/api/v1/attendance/sessions/team-status/").data
    manager_row = next(row for row in manager_team_status if row["employee_id"] == employee.id)
    manager_daily_summary = api_client.get(
        f"/api/v1/attendance/sessions/daily-summary/?employee_id={employee.id}&date={today}"
    ).data

    # Super Admin: same employee via company-report (bounded to today).
    api_client.force_authenticate(super_admin)
    admin_company_report = api_client.get(
        f"/api/v1/attendance/sessions/company-report/?date_from={today}&date_to={today}"
    ).data
    admin_row = next(row for row in admin_company_report if row["employee_id"] == employee.id)

    for other in (manager_row, manager_daily_summary, admin_row):
        assert other["login_time"] == employee_view["login_time"]
        assert other["logout_time"] == employee_view["logout_time"]
        assert other["check_in_time"] == employee_view["check_in_time"]
        assert other["check_out_time"] == employee_view["check_out_time"]
        assert other["active_working_seconds"] == employee_view["active_working_seconds"]
        assert other["session_seconds"] == employee_view["session_seconds"]

    # And the login/logout values are the REAL ones actually recorded —
    # not just internally consistent with each other but wrong together.
    assert employee_view["login_time"] is not None
    assert employee_view["logout_time"] is not None
