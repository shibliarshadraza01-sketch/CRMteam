"""CP19: end-to-end tests for the system API. Requires a real database."""
import pytest

from apps.system.models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting

pytestmark = pytest.mark.django_db

AUDIT_LOGS_URL = "/api/v1/system/audit-logs/"
SETTINGS_URL = "/api/v1/system/settings/"
FLAGS_URL = "/api/v1/system/feature-flags/"
JOBS_URL = "/api/v1/system/background-jobs/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# AuditLog — Manager+ read-only
# --------------------------------------------------------------------------


def test_unauthenticated_denied(api_client):
    response = api_client.get(AUDIT_LOGS_URL)
    assert response.status_code == 401


def test_employee_cannot_view_audit_logs(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.get(AUDIT_LOGS_URL)
    assert response.status_code == 403


def test_manager_can_view_audit_logs(api_client, manager, employee, customer):
    api_client.force_authenticate(manager)
    response = api_client.get(AUDIT_LOGS_URL)
    assert response.status_code == 200


def test_audit_log_has_no_write_endpoint(api_client, manager):
    api_client.force_authenticate(manager)
    response = api_client.post(AUDIT_LOGS_URL, {"action": "OTHER"})
    assert response.status_code == 405


def test_manager_sees_full_audit_trail_not_just_own(api_client, manager, employee, other_employee, organization):
    """AuditLogViewSet is role-gated, NOT ownership-scoped — a Manager
    sees every entry, not just entries tied to their own managed team.
    """
    from apps.crm.models import Customer

    Customer.objects.create(organization=organization, name="A", slug="a", owner=employee)
    Customer.objects.create(organization=organization, name="B", slug="b", owner=other_employee)
    api_client.force_authenticate(manager)

    response = api_client.get(AUDIT_LOGS_URL)

    assert response.data["count"] == 2


# --------------------------------------------------------------------------
# SystemSetting / FeatureFlag — shared config, read/write split
# --------------------------------------------------------------------------


def test_employee_can_read_settings(api_client, employee, setting):
    api_client.force_authenticate(employee)
    response = api_client.get(SETTINGS_URL)
    assert response.status_code == 200


def test_employee_cannot_create_setting(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(SETTINGS_URL, {"key": "x", "value": 1})
    assert response.status_code == 403


def test_manager_can_create_setting(api_client, manager):
    api_client.force_authenticate(manager)
    response = api_client.post(SETTINGS_URL, {"key": "x", "value": 1})
    assert response.status_code == 201


def test_manager_can_create_feature_flag(api_client, manager):
    api_client.force_authenticate(manager)
    response = api_client.post(FLAGS_URL, {"key": "x", "name": "X"})
    assert response.status_code == 201


def test_feature_flag_rejects_invalid_rollout_percentage(api_client, manager):
    api_client.force_authenticate(manager)
    response = api_client.post(FLAGS_URL, {"key": "x", "name": "X", "rollout_percentage": 150})
    assert response.status_code == 400


# --------------------------------------------------------------------------
# BackgroundJob — owner-scoped, lifecycle actions
# --------------------------------------------------------------------------


def test_employee_can_create_job_and_owns_it_by_default(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(JOBS_URL, {"name": "Export", "job_type": "EXPORT"})
    assert response.status_code == 201
    assert response.data["owner"] == employee.id
    assert response.data["status"] == "PENDING"


def test_employee_cannot_see_another_employees_job(api_client, employee, other_employee):
    BackgroundJob.objects.create(name="Theirs", job_type="X", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(JOBS_URL)

    assert response.data["count"] == 0


def test_start_complete_lifecycle(api_client, employee, job):
    api_client.force_authenticate(employee)

    start_response = api_client.post(f"{_detail(JOBS_URL, job.pk)}start/")
    assert start_response.status_code == 200
    assert start_response.data["status"] == "RUNNING"

    complete_response = api_client.post(
        f"{_detail(JOBS_URL, job.pk)}complete/", {"result_data": {"rows": 5}}, format="json"
    )
    assert complete_response.status_code == 200
    assert complete_response.data["status"] == "COMPLETED"
    assert complete_response.data["result_data"] == {"rows": 5}


def test_start_rejects_already_running(api_client, employee, job):
    api_client.force_authenticate(employee)
    api_client.post(f"{_detail(JOBS_URL, job.pk)}start/")

    response = api_client.post(f"{_detail(JOBS_URL, job.pk)}start/")

    assert response.status_code == 400


def test_fail_action(api_client, employee, job):
    api_client.force_authenticate(employee)
    api_client.post(f"{_detail(JOBS_URL, job.pk)}start/")

    response = api_client.post(f"{_detail(JOBS_URL, job.pk)}fail/", {"error_message": "boom"})

    assert response.status_code == 200
    assert response.data["status"] == "FAILED"
    assert response.data["error_message"] == "boom"


def test_status_cannot_be_set_via_plain_patch(api_client, employee, job):
    api_client.force_authenticate(employee)
    response = api_client.patch(_detail(JOBS_URL, job.pk), {"status": "COMPLETED"})
    assert response.status_code == 200
    assert response.data["status"] == "PENDING"  # read-only field, ignored


# --------------------------------------------------------------------------
# Pagination
# --------------------------------------------------------------------------


def test_pagination_default_page_size_is_20(api_client, manager):
    for i in range(25):
        SystemSetting.objects.create(key=f"k{i:03d}", value=i)
    api_client.force_authenticate(manager)

    response = api_client.get(SETTINGS_URL)

    assert len(response.data["results"]) == 20
    assert response.data["count"] == 25
