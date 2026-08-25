"""Staff-management pass: the Super Admin's User/Staff Management surface.

Covers the profile fields (username/phone/joining date/status), MANAGER
ASSIGNMENT via the apps.organization Team/Membership hierarchy, the
non-destructive delete semantics, the consolidated staff profile endpoint,
and the security-change verification placeholder.

`department` was removed from the User model — it was a free-text label
nothing in the application read or scoped by. (apps.organization.Department,
the org-hierarchy model, is a different concept and is unaffected.)
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
            "role": django_user_model.Role.EMPLOYEE,
            "is_active": True,
        },
        format="json",
    )

    assert response.status_code == 201
    created = django_user_model.objects.get(email="new-hire@example.com")
    assert created.username == "newhire"
    assert created.phone == "+15550100"
    assert not hasattr(created, "department")
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


# --------------------------------------------------------------------------
# Manager assignment
#
# An Employee's manager is stored as an apps.organization Membership on a
# Team that Manager leads — the SAME rows apps.crm.services.managed_user_ids()
# scopes every list query by. These tests assert the assignment is genuinely
# persisted and RBAC-effective, not merely displayed.
# --------------------------------------------------------------------------


def test_super_admin_can_assign_a_manager_at_creation(api_client, super_admin, manager, django_user_model):
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        USERS_URL,
        {
            "email": "assigned@example.com",
            "password": "a-strong-password",
            "first_name": "Assigned",
            "last_name": "Employee",
            "role": django_user_model.Role.EMPLOYEE,
            "manager": manager.pk,
        },
        format="json",
    )

    assert response.status_code == 201
    from apps.accounts.services import get_manager_for_user

    created = django_user_model.objects.get(email="assigned@example.com")
    assert get_manager_for_user(created) == manager


def test_super_admin_can_assign_a_manager_on_edit(api_client, super_admin, manager, employee):
    from apps.accounts.services import get_manager_for_user

    api_client.force_authenticate(super_admin)

    response = api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": manager.pk}, format="json")

    assert response.status_code == 200
    assert response.data["manager"] == manager.pk
    employee.refresh_from_db()
    assert get_manager_for_user(employee) == manager


def test_assignment_is_visible_in_both_directions(api_client, super_admin, manager, employee):
    from apps.accounts.services import get_employees_for_manager, get_manager_for_user

    api_client.force_authenticate(super_admin)
    api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": manager.pk}, format="json")

    assert get_manager_for_user(employee) == manager
    assert list(get_employees_for_manager(manager)) == [employee]


def test_assignment_actually_widens_that_managers_rbac_scope(api_client, super_admin, manager, employee):
    """The point of reusing Team/Membership: the assignment must take
    effect in the one scoping mechanism the whole app already uses.
    """
    from apps.crm.services import managed_user_ids

    assert employee.pk not in managed_user_ids(manager)

    api_client.force_authenticate(super_admin)
    api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": manager.pk}, format="json")

    assert employee.pk in managed_user_ids(manager)


def test_assigning_null_clears_the_manager(api_client, super_admin, manager, employee):
    from apps.accounts.services import get_manager_for_user

    api_client.force_authenticate(super_admin)
    api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": manager.pk}, format="json")
    assert get_manager_for_user(employee) == manager

    response = api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": None}, format="json")

    assert response.status_code == 200
    assert get_manager_for_user(employee) is None


def test_reassignment_does_not_leave_the_employee_on_two_teams(
    api_client, super_admin, manager, employee, django_user_model
):
    from apps.accounts.services import get_employees_for_manager, get_manager_for_user

    other_manager = django_user_model.objects.create_user(
        email="second-manager@example.com", password="manager-pass-123", role=django_user_model.Role.MANAGER
    )
    api_client.force_authenticate(super_admin)
    api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": manager.pk}, format="json")

    api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": other_manager.pk}, format="json")

    assert get_manager_for_user(employee) == other_manager
    # The previous manager must lose visibility, not keep it alongside.
    assert list(get_employees_for_manager(manager)) == []
    assert list(get_employees_for_manager(other_manager)) == [employee]


def test_a_nonexistent_manager_is_rejected(api_client, super_admin, employee):
    api_client.force_authenticate(super_admin)

    response = api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": 999999}, format="json")

    assert response.status_code == 400
    assert "manager" in response.data


def test_a_non_manager_user_cannot_be_used_as_a_manager(api_client, super_admin, employee, django_user_model):
    other_employee = django_user_model.objects.create_user(
        email="peer@example.com", password="employee-pass-123", role=django_user_model.Role.EMPLOYEE
    )
    api_client.force_authenticate(super_admin)

    response = api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": other_employee.pk}, format="json")

    assert response.status_code == 400
    assert "manager" in response.data


def test_a_user_cannot_be_their_own_manager(api_client, super_admin, manager):
    api_client.force_authenticate(super_admin)

    response = api_client.patch(f"{USERS_URL}{manager.pk}/", {"manager": manager.pk}, format="json")

    assert response.status_code == 400
    assert "manager" in response.data


def test_an_employee_cannot_assign_a_manager(api_client, employee, manager):
    """RBAC is not weakened to make the feature work."""
    api_client.force_authenticate(employee)

    response = api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": manager.pk}, format="json")

    assert response.status_code == 403


def test_staff_profile_reports_the_manager_and_no_department(api_client, super_admin, manager, employee):
    api_client.force_authenticate(super_admin)
    api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": manager.pk}, format="json")

    response = api_client.get(f"{USERS_URL}{employee.pk}/profile/")

    assert response.status_code == 200
    assert "department" not in response.data["profile"]
    assert response.data["profile"]["manager"]["id"] == manager.pk


def test_user_list_no_longer_exposes_department(api_client, super_admin, employee):
    api_client.force_authenticate(super_admin)

    response = api_client.get(f"{USERS_URL}{employee.pk}/")

    assert response.status_code == 200
    assert "department" not in response.data
    assert "manager" in response.data


# --------------------------------------------------------------------------
# Manager-assignment ERROR MESSAGES
#
# Every rejection above used to answer with one identical, factually false
# sentence: `Invalid pk "4" - object does not exist.` — about a manager the
# Super Admin could plainly see in the very list they picked from. The cause
# was ManagerAssignmentField restricting its own queryset, so
# PrimaryKeyRelatedField rejected the pk before the specific checks in
# validate() could run at all (they were unreachable dead code).
#
# These tests pin the messages, not just the 400, because "the request was
# rejected" was never the part that was broken.
# --------------------------------------------------------------------------


def _manager_error(response):
    return " ".join(str(message) for message in response.data["manager"])


def test_assigning_a_peer_employee_says_they_are_not_a_manager(
    api_client, super_admin, employee, django_user_model
):
    peer = django_user_model.objects.create_user(
        email="peer-msg@example.com",
        password="employee-pass-123",
        role=django_user_model.Role.EMPLOYEE,
        first_name="Peer",
        last_name="Person",
    )
    api_client.force_authenticate(super_admin)

    response = api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": peer.pk}, format="json")

    assert response.status_code == 400
    message = _manager_error(response)
    assert "not a manager" in message
    assert "does not exist" not in message
    # The offending user is named, so the admin knows which pick was wrong.
    assert "Peer Person" in message


def test_assigning_a_deactivated_manager_says_so_and_how_to_fix_it(
    api_client, super_admin, employee, django_user_model
):
    """The message an admin most needs: the account is real, it is simply
    deactivated, and here is what to do about it.
    """
    dormant = django_user_model.objects.create_user(
        email="dormant@example.com",
        password="manager-pass-123",
        role=django_user_model.Role.MANAGER,
        first_name="Dormant",
        last_name="Manager",
        is_active=False,
    )
    api_client.force_authenticate(super_admin)

    response = api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": dormant.pk}, format="json")

    assert response.status_code == 400
    message = _manager_error(response)
    assert "deactivated" in message
    assert "Reactivate" in message
    assert "does not exist" not in message


def test_self_assignment_says_so_rather_than_denying_the_user_exists(
    api_client, super_admin, employee
):
    api_client.force_authenticate(super_admin)

    response = api_client.patch(
        f"{USERS_URL}{employee.pk}/", {"manager": employee.pk}, format="json"
    )

    assert response.status_code == 400
    message = _manager_error(response)
    assert "their own manager" in message
    assert "does not exist" not in message


def test_does_not_exist_is_reserved_for_a_pk_that_really_does_not_exist(
    api_client, super_admin, employee
):
    api_client.force_authenticate(super_admin)

    response = api_client.patch(f"{USERS_URL}{employee.pk}/", {"manager": 999999}, format="json")

    assert response.status_code == 400
    assert "does not exist" in _manager_error(response)


def test_a_deactivated_manager_is_rejected_at_CREATE_time_too(
    api_client, super_admin, django_user_model
):
    """Create and edit must enforce the SAME rules — the create path used
    to be the looser of the two by simply having fewer checks written out.
    """
    dormant = django_user_model.objects.create_user(
        email="dormant-create@example.com",
        password="manager-pass-123",
        role=django_user_model.Role.MANAGER,
        is_active=False,
    )
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        USERS_URL,
        {
            "email": "new-report@example.com",
            "password": "a-strong-password",
            "role": django_user_model.Role.EMPLOYEE,
            "manager": dormant.pk,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "deactivated" in _manager_error(response)
    assert not django_user_model.objects.filter(email="new-report@example.com").exists()


def test_a_peer_employee_is_rejected_at_CREATE_time_too(
    api_client, super_admin, employee, django_user_model
):
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        USERS_URL,
        {
            "email": "new-report-2@example.com",
            "password": "a-strong-password",
            "role": django_user_model.Role.EMPLOYEE,
            "manager": employee.pk,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "not a manager" in _manager_error(response)


def test_the_offered_manager_choices_exclude_deactivated_accounts(
    manager, django_user_model
):
    """The list the API advertises and the list it accepts must be the
    same list — that is the whole point of `selectable_managers()`.
    """
    from apps.accounts.serializers import selectable_managers

    dormant = django_user_model.objects.create_user(
        email="dormant-choices@example.com",
        password="manager-pass-123",
        role=django_user_model.Role.MANAGER,
        is_active=False,
    )

    selectable = list(selectable_managers())

    assert manager in selectable
    assert dormant not in selectable
