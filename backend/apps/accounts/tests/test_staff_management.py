"""Staff-management pass: the Super Admin's User/Staff Management surface.

Covers the new profile fields (username/phone/department/joining date/
status), the non-destructive delete semantics, the consolidated staff
profile endpoint, and the security-change verification placeholder.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounts.verification import (
    CHANGE_PASSWORD,
    SecurityVerificationRequired,
    describe_security_verification,
    verify_security_change,
)

USERS_URL = "/api/v1/auth/users/"
SECURITY_URL = "/api/v1/auth/settings/security/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="staff-admin@example.com", password="admin-pass-123", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="staff-manager@example.com", password="manager-pass-123", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="staff-employee@example.com", password="employee-pass-123", role=django_user_model.Role.EMPLOYEE
    )


# --------------------------------------------------------------------------
# Creation form fields
# --------------------------------------------------------------------------


def test_super_admin_creates_a_staff_account_with_all_profile_fields(api_client, super_admin, django_user_model):
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        USERS_URL,
        {
            "email": "new-hire@example.com",
            "password": "a-strong-password",
            "username": "newhire",
            "first_name": "New",
            "last_name": "Hire",
            "phone": "+15550100",
            "department": "Sales",
            "role": django_user_model.Role.EMPLOYEE,
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == 201
    created = django_user_model.objects.get(email="new-hire@example.com")
    assert created.username == "newhire"
    assert created.phone == "+15550100"
    assert created.department == "Sales"
    assert created.role == django_user_model.Role.EMPLOYEE
    # The password is never echoed back.
    assert "password" not in response.data


def test_username_is_not_an_authentication_credential(api_client, django_user_model):
    """Explicit guard on this phase's judgment call: ``username`` is a
    PROFILE field. Login is, and remains, email + password.
    """
    django_user_model.objects.create_user(
        email="handle@example.com", password="a-strong-password", username="handle",
        role=django_user_model.Role.EMPLOYEE,
    )

    by_username = api_client.post(
        "/api/v1/auth/login/", {"email": "handle", "password": "a-strong-password"}, format="json"
    )
    assert by_username.status_code == 400  # not even a valid EmailField value

    by_email = api_client.post(
        "/api/v1/auth/login/", {"email": "handle@example.com", "password": "a-strong-password"}, format="json"
    )
    assert by_email.status_code == 200


def test_blank_usernames_do_not_collide(db, django_user_model):
    """Two accounts with no username must both be creatable — an empty
    username is stored as NULL, and NULLs never collide under a unique
    constraint.
    """
    django_user_model.objects.create_user(email="a@example.com", password="x")
    django_user_model.objects.create_user(email="b@example.com", password="x")

    assert django_user_model.objects.filter(username__isnull=True).count() == 2


def test_username_must_be_unique_when_set(db, django_user_model):
    from django.core.exceptions import ValidationError

    django_user_model.objects.create_user(email="c@example.com", password="x", username="taken")

    with pytest.raises(ValidationError):
        django_user_model.objects.create_user(email="d@example.com", password="x", username="taken")


def test_manager_cannot_create_staff_accounts(api_client, manager):
    api_client.force_authenticate(manager)

    response = api_client.post(
        USERS_URL, {"email": "nope@example.com", "password": "a-strong-password"}, format="json"
    )

    assert response.status_code == 403


# --------------------------------------------------------------------------
# Deactivate / "delete" semantics
# --------------------------------------------------------------------------


def test_delete_deactivates_and_never_removes_the_row(api_client, super_admin, employee, django_user_model):
    api_client.force_authenticate(super_admin)

    response = api_client.delete(f"{USERS_URL}{employee.pk}/")

    assert response.status_code == 200
    assert django_user_model.objects.filter(pk=employee.pk).exists()
    employee.refresh_from_db()
    assert employee.is_active is False


def test_delete_preserves_the_users_historical_records(api_client, super_admin, employee):
    """A "deleted" staff member's owned business records must survive with
    their attribution intact — the whole reason hard delete is refused.
    """
    from apps.crm.models import Lead

    lead = Lead.objects.create(company_name="Legacy Co", contact_name="Ada", owner=employee)
    api_client.force_authenticate(super_admin)

    api_client.delete(f"{USERS_URL}{employee.pk}/")

    lead.refresh_from_db()
    assert lead.owner_id == employee.pk


def test_deactivated_user_cannot_log_in(api_client, super_admin, employee):
    api_client.force_authenticate(super_admin)
    api_client.post(f"{USERS_URL}{employee.pk}/deactivate/")

    api_client.force_authenticate(None)
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": "staff-employee@example.com", "password": "employee-pass-123"},
        format="json",
    )

    assert response.status_code == 401


def test_reactivation_restores_login(api_client, super_admin, employee):
    api_client.force_authenticate(super_admin)
    api_client.post(f"{USERS_URL}{employee.pk}/deactivate/")
    api_client.post(f"{USERS_URL}{employee.pk}/activate/")

    api_client.force_authenticate(None)
    response = api_client.post(
        "/api/v1/auth/login/",
        {"email": "staff-employee@example.com", "password": "employee-pass-123"},
        format="json",
    )

    assert response.status_code == 200


# --------------------------------------------------------------------------
# Staff profile
# --------------------------------------------------------------------------


def test_super_admin_can_read_any_staff_profile(api_client, super_admin, employee):
    api_client.force_authenticate(super_admin)

    response = api_client.get(f"{USERS_URL}{employee.pk}/profile/")

    assert response.status_code == 200
    assert response.data["profile"]["id"] == employee.pk
    for block in ("lead_performance", "converted_customers", "interaction_history", "work_activity"):
        assert block in response.data


def test_lead_performance_counts_are_real(api_client, super_admin, employee, db):
    from apps.crm.models import Lead

    Lead.objects.create(company_name="A", contact_name="A", owner=employee)
    Lead.objects.create(company_name="B", contact_name="B", owner=employee)
    api_client.force_authenticate(super_admin)

    performance = api_client.get(f"{USERS_URL}{employee.pk}/profile/").data["lead_performance"]

    assert performance["total_assigned"] == 2
    assert performance["converted"] == 0
    assert performance["conversion_rate"] == 0.0


def test_employee_cannot_read_another_users_profile(api_client, employee, manager):
    api_client.force_authenticate(employee)

    response = api_client.get(f"{USERS_URL}{manager.pk}/profile/")

    assert response.status_code == 404


def test_employee_can_read_their_own_profile(api_client, employee):
    api_client.force_authenticate(employee)

    response = api_client.get(f"{USERS_URL}{employee.pk}/profile/")

    assert response.status_code == 200


def test_manager_can_read_their_own_team_members_profile(api_client, manager, employee, db):
    from apps.organization.models import Department, Membership, Organization, Team

    organization = Organization.objects.create(name="Profile Org", slug="profile-org")
    department = Department.objects.create(organization=organization, name="Sales")
    team = Team.objects.create(department=department, name="Alpha", manager=manager)
    Membership.objects.create(user=employee, team=team)
    api_client.force_authenticate(manager)

    assert api_client.get(f"{USERS_URL}{employee.pk}/profile/").status_code == 200


def test_manager_cannot_read_an_out_of_scope_profile(api_client, manager, employee):
    api_client.force_authenticate(manager)

    assert api_client.get(f"{USERS_URL}{employee.pk}/profile/").status_code == 404


# --------------------------------------------------------------------------
# Security-change verification placeholder
# --------------------------------------------------------------------------


def test_verification_provider_is_described(api_client, super_admin):
    api_client.force_authenticate(super_admin)

    response = api_client.get(SECURITY_URL)

    assert response.status_code == 200
    assert response.data["method"] == "current_password"
    assert "current_password" in response.data["required_fields"]


def test_security_change_is_refused_without_verification(api_client, super_admin):
    api_client.force_authenticate(super_admin)

    response = api_client.post(SECURITY_URL, {"new_password": "another-strong-password"}, format="json")

    assert response.status_code == 403
    super_admin.refresh_from_db()
    assert super_admin.check_password("admin-pass-123")


def test_security_change_is_refused_with_a_wrong_verification_factor(api_client, super_admin):
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        SECURITY_URL,
        {"new_password": "another-strong-password", "current_password": "wrong"},
        format="json",
    )

    assert response.status_code == 403


def test_verified_security_change_is_applied(api_client, super_admin):
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        SECURITY_URL,
        {
            "username": "chief",
            "new_password": "another-strong-password",
            "current_password": "admin-pass-123",
        },
        format="json",
    )

    assert response.status_code == 200
    assert set(response.data["updated_fields"]) == {"username", "password"}
    super_admin.refresh_from_db()
    assert super_admin.username == "chief"
    assert super_admin.check_password("another-strong-password")


def test_security_response_never_echoes_secrets(api_client, super_admin):
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        SECURITY_URL,
        {"new_access_code": "code-123456", "current_password": "admin-pass-123"},
        format="json",
    )

    assert response.status_code == 200
    body = str(response.data)
    assert "code-123456" not in body
    assert "admin-pass-123" not in body
    super_admin.refresh_from_db()
    assert super_admin.check_access_code("code-123456")


def test_non_super_admin_cannot_set_an_access_code(api_client, manager):
    api_client.force_authenticate(manager)

    response = api_client.post(
        SECURITY_URL,
        {"new_access_code": "code-123456", "current_password": "manager-pass-123"},
        format="json",
    )

    assert response.status_code == 400


def test_a_request_with_nothing_to_change_is_rejected(api_client, super_admin):
    api_client.force_authenticate(super_admin)

    response = api_client.post(SECURITY_URL, {"current_password": "admin-pass-123"}, format="json")

    assert response.status_code == 400


def test_verify_security_change_rejects_an_unknown_change_type(super_admin):
    with pytest.raises(SecurityVerificationRequired):
        verify_security_change(super_admin, "not-a-change-type", {"current_password": "admin-pass-123"})


def test_verify_security_change_accepts_the_correct_factor(super_admin):
    # Returns None (does not raise) — the whole contract of the seam.
    assert verify_security_change(super_admin, CHANGE_PASSWORD, {"current_password": "admin-pass-123"}) is None


def test_unknown_provider_name_falls_back_to_the_safe_default(monkeypatch):
    monkeypatch.setenv("SECURITY_VERIFICATION_PROVIDER", "totally-made-up")

    assert describe_security_verification()["method"] == "current_password"
