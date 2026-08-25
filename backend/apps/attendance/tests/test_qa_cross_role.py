import pytest

from apps.attendance.models import AttendanceSession


def _auth(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
def test_cross_role_sees_identical_session_timestamps(api_client, employee, manager, super_admin, team, shift_config):
    """QA acceptance check: a real login->logout session must show the
    exact same login_at/logout_at to the Employee (self), their Manager
    (via team membership), and the Super Admin.
    """
    _auth(api_client, employee)

    r = api_client.post("/api/v1/attendance/sessions/start/")
    assert r.status_code == 201, r.data

    r2 = api_client.post("/api/v1/attendance/sessions/end/")
    assert r2.status_code == 200, r2.data

    session = AttendanceSession.objects.filter(employee=employee).order_by("-login_at").first()
    assert session is not None
    assert session.logout_at is not None

    def fetch(user):
        from rest_framework.test import APIClient

        c = APIClient()
        c.force_authenticate(user=user)
        resp = c.get(f"/api/v1/attendance/sessions/{session.id}/")
        return resp.status_code, resp.data

    results = {}
    for label, user in [("EMPLOYEE", employee), ("MANAGER", manager), ("SUPER_ADMIN", super_admin)]:
        status_code, data = fetch(user)
        results[label] = (status_code, data)

    for label, (status_code, data) in results.items():
        assert status_code == 200, f"{label} could not view session: {data}"

    login_ats = {label: data["login_at"] for label, (sc, data) in results.items()}
    logout_ats = {label: data["logout_at"] for label, (sc, data) in results.items()}
    assert len(set(login_ats.values())) == 1, login_ats
    assert len(set(logout_ats.values())) == 1, logout_ats
