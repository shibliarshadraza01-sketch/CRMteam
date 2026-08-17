"""Final-completion-pass: end-to-end tests for the organization hierarchy
API. Requires a real database.
"""
import pytest

from apps.organization.models import Department, Membership, Organization, Team

pytestmark = pytest.mark.django_db

ORGANIZATIONS_URL = "/api/v1/organization/organizations/"
DEPARTMENTS_URL = "/api/v1/organization/departments/"
TEAMS_URL = "/api/v1/organization/teams/"
MEMBERSHIPS_URL = "/api/v1/organization/memberships/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# Organization: read any authenticated, write Super Admin only
# --------------------------------------------------------------------------


def test_unauthenticated_denied(api_client):
    response = api_client.get(ORGANIZATIONS_URL)
    assert response.status_code == 401


def test_employee_can_list_organizations(api_client, employee, organization):
    api_client.force_authenticate(employee)
    response = api_client.get(ORGANIZATIONS_URL)
    assert response.status_code == 200
    assert response.data["count"] == 1


def test_employee_cannot_create_organization(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(ORGANIZATIONS_URL, {"name": "New Co", "slug": "new-co"})
    assert response.status_code == 403


def test_manager_cannot_create_organization(api_client, manager):
    api_client.force_authenticate(manager)
    response = api_client.post(ORGANIZATIONS_URL, {"name": "New Co", "slug": "new-co"})
    assert response.status_code == 403


def test_super_admin_can_create_organization(api_client, super_admin):
    api_client.force_authenticate(super_admin)
    response = api_client.post(ORGANIZATIONS_URL, {"name": "New Co", "slug": "new-co"})
    assert response.status_code == 201
    assert Organization.objects.filter(slug="new-co").exists()


def test_filter_organizations_by_is_active(api_client, employee):
    Organization.objects.create(name="Active Co", slug="active-co", is_active=True)
    Organization.objects.create(name="Inactive Co", slug="inactive-co", is_active=False)
    api_client.force_authenticate(employee)

    response = api_client.get(ORGANIZATIONS_URL, {"is_active": "false"})
    names = {row["name"] for row in response.data["results"]}
    assert names == {"Inactive Co"}


# --------------------------------------------------------------------------
# Department / Team: read any authenticated, write Manager or above
# --------------------------------------------------------------------------


def test_employee_can_list_departments(api_client, employee, department):
    api_client.force_authenticate(employee)
    response = api_client.get(DEPARTMENTS_URL)
    assert response.status_code == 200
    assert response.data["count"] == 1


def test_employee_cannot_create_department(api_client, employee, organization):
    api_client.force_authenticate(employee)
    response = api_client.post(DEPARTMENTS_URL, {"organization": organization.pk, "name": "Support"})
    assert response.status_code == 403


def test_manager_can_create_department(api_client, manager, organization):
    api_client.force_authenticate(manager)
    response = api_client.post(DEPARTMENTS_URL, {"organization": organization.pk, "name": "Support"})
    assert response.status_code == 201
    assert Department.objects.filter(name="Support").exists()


def test_department_detail_serializer_includes_organization_name(api_client, employee, department):
    api_client.force_authenticate(employee)
    response = api_client.get(_detail(DEPARTMENTS_URL, department.pk))
    assert response.data["organization_name"] == department.organization.name


def test_manager_can_create_team(api_client, manager, department):
    api_client.force_authenticate(manager)
    response = api_client.post(TEAMS_URL, {"department": department.pk, "name": "New Team"})
    assert response.status_code == 201
    assert Team.objects.filter(name="New Team").exists()


def test_employee_cannot_delete_team(api_client, employee, team):
    api_client.force_authenticate(employee)
    response = api_client.delete(_detail(TEAMS_URL, team.pk))
    assert response.status_code == 403


def test_manager_can_delete_team_and_it_is_a_real_delete(api_client, manager, team):
    """No soft delete for this app (see models.py) — DELETE removes the row
    permanently.
    """
    api_client.force_authenticate(manager)
    response = api_client.delete(_detail(TEAMS_URL, team.pk))
    assert response.status_code == 204
    assert not Team.objects.filter(pk=team.pk).exists()


# --------------------------------------------------------------------------
# Membership: ownership-scoped like every CP10 resource
# --------------------------------------------------------------------------


def test_employee_sees_only_their_own_membership(api_client, employee, manager, team):
    Membership.objects.create(user=employee, team=team)
    other_employee = employee.__class__.objects.create_user(
        email="other-org-employee@example.com", password="x", role=employee.__class__.Role.EMPLOYEE
    )
    Membership.objects.create(user=other_employee, team=team)

    api_client.force_authenticate(employee)
    response = api_client.get(MEMBERSHIPS_URL)

    assert response.data["count"] == 1
    assert response.data["results"][0]["user"] == employee.id


def test_manager_sees_memberships_of_teams_they_manage(api_client, manager, team, employee):
    """``team``'s fixture already assigns ``manager`` as its manager."""
    Membership.objects.create(user=employee, team=team)

    api_client.force_authenticate(manager)
    response = api_client.get(MEMBERSHIPS_URL)

    assert response.data["count"] == 1
    assert response.data["results"][0]["user"] == employee.id


def test_super_admin_sees_every_membership(api_client, super_admin, team, employee):
    Membership.objects.create(user=employee, team=team)

    api_client.force_authenticate(super_admin)
    response = api_client.get(MEMBERSHIPS_URL)

    assert response.data["count"] == 1


def test_employee_can_view_their_own_membership_detail(api_client, employee, team):
    membership = Membership.objects.create(user=employee, team=team)

    api_client.force_authenticate(employee)
    response = api_client.get(_detail(MEMBERSHIPS_URL, membership.pk))

    assert response.status_code == 200
    assert response.data["team_name"] == team.name
