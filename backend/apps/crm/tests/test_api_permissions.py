"""CP10: tests for the "Employees see own records only; Managers see their
team's records; Super Admin sees everything" rule — the centerpiece of
CP10's permission requirements, built entirely from CP6's
``IsOwnerOrSuperAdmin`` plus the new ``scope_queryset_for_user()``/
``manager_has_access()`` (composing CP8's ``Team``/``Membership``, no new
role-comparison logic). Requires a real database.
"""
import pytest

from apps.crm.models import Customer

pytestmark = pytest.mark.django_db

CUSTOMERS_URL = "/api/v1/crm/customers/"


def _detail(pk):
    return f"{CUSTOMERS_URL}{pk}/"


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------


def test_unauthenticated_request_denied(api_client):
    response = api_client.get(CUSTOMERS_URL)
    assert response.status_code == 401


def test_authenticated_request_allowed(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.get(CUSTOMERS_URL)
    assert response.status_code == 200


# --------------------------------------------------------------------------
# Employees: own records only
# --------------------------------------------------------------------------


def test_employee_list_only_shows_own_customers(api_client, organization, employee, other_employee):
    Customer.objects.create(organization=organization, name="Mine", slug="mine", owner=employee)
    Customer.objects.create(organization=organization, name="Theirs", slug="theirs", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(CUSTOMERS_URL)

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Mine"}


def test_employee_cannot_retrieve_someone_elses_customer(api_client, organization, employee, other_employee):
    theirs = Customer.objects.create(organization=organization, name="Theirs", slug="theirs", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(_detail(theirs.pk))

    assert response.status_code == 404  # not visible, not merely forbidden


def test_employee_cannot_patch_someone_elses_customer(api_client, organization, employee, other_employee):
    theirs = Customer.objects.create(organization=organization, name="Theirs", slug="theirs", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.patch(_detail(theirs.pk), {"industry": "Hacked"})

    assert response.status_code == 404


def test_employee_can_retrieve_their_own_customer(api_client, organization, employee):
    mine = Customer.objects.create(organization=organization, name="Mine", slug="mine", owner=employee)
    api_client.force_authenticate(employee)

    response = api_client.get(_detail(mine.pk))

    assert response.status_code == 200


# --------------------------------------------------------------------------
# Managers: their team's records
# --------------------------------------------------------------------------


def test_manager_sees_own_and_team_members_customers(api_client, organization, manager, employee, managed_team):
    mine = Customer.objects.create(organization=organization, name="Mine", slug="mine", owner=manager)
    team_members = Customer.objects.create(organization=organization, name="TeamMembers", slug="team-members", owner=employee)
    api_client.force_authenticate(manager)

    response = api_client.get(CUSTOMERS_URL)

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Mine", "TeamMembers"}


def test_manager_does_not_see_unrelated_employees_customer(api_client, organization, manager, other_employee, managed_team):
    Customer.objects.create(organization=organization, name="Unrelated", slug="unrelated", owner=other_employee)
    api_client.force_authenticate(manager)

    response = api_client.get(CUSTOMERS_URL)

    names = {row["name"] for row in response.data["results"]}
    assert "Unrelated" not in names


def test_manager_can_retrieve_and_patch_a_team_members_customer(api_client, organization, manager, employee, managed_team):
    theirs = Customer.objects.create(organization=organization, name="TeamMembers", slug="team-members", owner=employee)
    api_client.force_authenticate(manager)

    get_response = api_client.get(_detail(theirs.pk))
    patch_response = api_client.patch(_detail(theirs.pk), {"industry": "Retail"})

    assert get_response.status_code == 200
    assert patch_response.status_code == 200


def test_manager_of_a_different_team_cannot_access_the_customer(api_client, organization, employee, managed_team, django_user_model):
    other_manager = django_user_model.objects.create_user(
        email="other-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    theirs = Customer.objects.create(organization=organization, name="TeamMembers", slug="team-members", owner=employee)
    api_client.force_authenticate(other_manager)

    response = api_client.get(_detail(theirs.pk))

    assert response.status_code == 404


# --------------------------------------------------------------------------
# Super Admin: everything
# --------------------------------------------------------------------------


def test_super_admin_sees_every_customer_regardless_of_owner(api_client, organization, employee, other_employee, manager, super_admin):
    Customer.objects.create(organization=organization, name="A", slug="a", owner=employee)
    Customer.objects.create(organization=organization, name="B", slug="b", owner=other_employee)
    Customer.objects.create(organization=organization, name="C", slug="c", owner=manager)
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL)

    names = {row["name"] for row in response.data["results"]}
    assert names == {"A", "B", "C"}


def test_super_admin_can_retrieve_and_delete_anyones_customer(api_client, organization, employee, super_admin):
    theirs = Customer.objects.create(organization=organization, name="Theirs", slug="theirs", owner=employee)
    api_client.force_authenticate(super_admin)

    get_response = api_client.get(_detail(theirs.pk))
    delete_response = api_client.delete(_detail(theirs.pk))

    assert get_response.status_code == 200
    assert delete_response.status_code == 204


# --------------------------------------------------------------------------
# restore/hard-delete gating (CanRestoreOrHardDelete, CP7)
# --------------------------------------------------------------------------


def test_employee_cannot_hard_delete_even_their_own_customer(api_client, organization, employee):
    mine = Customer.objects.create(organization=organization, name="Mine", slug="mine", owner=employee)
    api_client.force_authenticate(employee)

    response = api_client.post(f"{_detail(mine.pk)}hard-delete/")

    assert response.status_code == 403


def test_manager_cannot_hard_delete_another_teams_customer(api_client, organization, employee, django_user_model):
    # Final pre-production pass: CanRestoreOrHardDelete (CP7) still gates
    # restore/hard-delete by ROLE (Manager-or-above), but the underlying
    # queryset is now ALSO scoped via scope_queryset_for_user(), same as
    # every other action — a Manager may no longer restore/hard-delete a
    # record outside their own managed scope just by knowing its id. This
    # replaces the old "any Manager can hard-delete regardless of team"
    # test, which was asserting the bug this pass fixes (product decision:
    # Manager restore/hard-delete is scoped to their own team, not
    # company-wide). An out-of-scope object 404s, matching how
    # out-of-scope objects are hidden everywhere else in this codebase.
    unrelated_manager = django_user_model.objects.create_user(
        email="unrelated-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    theirs = Customer.objects.create(organization=organization, name="TeamMembers", slug="team-members", owner=employee)
    api_client.force_authenticate(unrelated_manager)

    response = api_client.post(f"{_detail(theirs.pk)}hard-delete/")

    assert response.status_code == 404


def test_manager_can_hard_delete_their_own_teams_customer(api_client, organization, managed_team, manager, employee):
    # Positive counterpart: a Manager CAN hard-delete a record owned by a
    # member of their own team (managed_team fixture: manager manages a
    # team that employee belongs to).
    theirs = Customer.objects.create(organization=organization, name="TeamMembers", slug="team-members-2", owner=employee)
    api_client.force_authenticate(manager)

    response = api_client.post(f"{_detail(theirs.pk)}hard-delete/")

    assert response.status_code == 204


def test_manager_cannot_restore_another_teams_customer(api_client, organization, employee, django_user_model):
    unrelated_manager = django_user_model.objects.create_user(
        email="unrelated-manager-2@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    theirs = Customer.objects.create(organization=organization, name="TeamMembers3", slug="team-members-3", owner=employee)
    theirs.soft_delete(updated_by=None)
    api_client.force_authenticate(unrelated_manager)

    response = api_client.post(f"{_detail(theirs.pk)}restore/")

    assert response.status_code == 404


def test_manager_can_restore_their_own_teams_customer(api_client, organization, managed_team, manager, employee):
    theirs = Customer.objects.create(organization=organization, name="TeamMembers4", slug="team-members-4", owner=employee)
    theirs.soft_delete(updated_by=None)
    api_client.force_authenticate(manager)

    response = api_client.post(f"{_detail(theirs.pk)}restore/")

    assert response.status_code == 200


def test_super_admin_can_restore_and_hard_delete_any_teams_customer(api_client, organization, employee, super_admin):
    a = Customer.objects.create(organization=organization, name="AdminScopeA", slug="admin-scope-a", owner=employee)
    a.soft_delete(updated_by=None)
    b = Customer.objects.create(organization=organization, name="AdminScopeB", slug="admin-scope-b", owner=employee)
    api_client.force_authenticate(super_admin)

    restore_response = api_client.post(f"{_detail(a.pk)}restore/")
    hard_delete_response = api_client.post(f"{_detail(b.pk)}hard-delete/")

    assert restore_response.status_code == 200
    assert hard_delete_response.status_code == 204
