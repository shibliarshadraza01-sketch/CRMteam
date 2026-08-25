"""Final production infrastructure pass, Part 15: regression tests for
the P2 finding from the prior security audit — every "create with an
optional explicit `owner`" endpoint accepted a client-supplied `owner`
id from ANY authenticated user, not just Manager+, letting an Employee
attribute a brand-new record to a different user.

Fixed by `apps.crm.services.resolve_owner_for_create()`, applied at
every affected `perform_create()` project-wide:

- Employee: `owner` must be themselves (or omitted, defaulting to self).
- Manager: `owner` may be themselves or anyone in their own
  `managed_user_ids()` (the same team-scoping boundary already enforced
  for reads).
- Super Admin: `owner` may be anyone.

Exercised here across Lead, Customer, and Task — one representative from
each of the two code shapes this fix touches (the `data.pop("owner")`
shape on Customer, and the `owner_id is None` shape on Lead/Task).
"""
import pytest
from rest_framework.test import APIClient

from apps.organization.models import Department, Membership, Organization, Team

pytestmark = pytest.mark.django_db

LEADS_URL = "/api/v1/crm/leads/"
CUSTOMERS_URL = "/api/v1/crm/customers/"
TASKS_URL = "/api/v1/activities/tasks/"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Owner Assignment Org", slug="owner-assignment-org")


@pytest.fixture
def employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="owner-fix-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="owner-fix-other@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="owner-fix-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="owner-fix-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def managed_team(db, organization, manager, employee):
    department = Department.objects.create(organization=organization, name="Owner Fix Dept")
    team = Team.objects.create(department=department, name="Owner Fix Team", manager=manager)
    Membership.objects.create(user=employee, team=team)
    return team


def test_employee_cannot_create_lead_owned_by_someone_else(api_client, employee, other_employee):
    api_client.force_authenticate(employee)
    response = api_client.post(
        LEADS_URL,
        {"company_name": "Co", "contact_name": "Contact", "owner": other_employee.pk},
    )
    assert response.status_code == 403


def test_employee_creating_lead_without_owner_defaults_to_self(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(LEADS_URL, {"company_name": "Co", "contact_name": "Contact"})
    assert response.status_code == 201
    assert response.data["owner"] == employee.pk


def test_employee_creating_lead_owned_by_self_explicitly_is_allowed(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(
        LEADS_URL, {"company_name": "Co", "contact_name": "Contact", "owner": employee.pk}
    )
    assert response.status_code == 201
    assert response.data["owner"] == employee.pk


def test_employee_cannot_create_customer_owned_by_someone_else(api_client, employee, other_employee, organization):
    api_client.force_authenticate(employee)
    response = api_client.post(
        CUSTOMERS_URL,
        {"organization": organization.pk, "name": "Acme", "owner": other_employee.pk},
    )
    assert response.status_code == 403


def test_employee_cannot_create_task_owned_by_someone_else(api_client, employee, other_employee):
    api_client.force_authenticate(employee)
    response = api_client.post(TASKS_URL, {"title": "Follow up", "owner": other_employee.pk})
    assert response.status_code == 403


def test_manager_can_create_lead_owned_by_their_own_team_member(api_client, manager, employee, managed_team):
    api_client.force_authenticate(manager)
    response = api_client.post(
        LEADS_URL, {"company_name": "Co", "contact_name": "Contact", "owner": employee.pk}
    )
    assert response.status_code == 201
    assert response.data["owner"] == employee.pk


def test_manager_cannot_create_lead_owned_by_an_unrelated_employee(api_client, manager, other_employee):
    api_client.force_authenticate(manager)
    response = api_client.post(
        LEADS_URL, {"company_name": "Co", "contact_name": "Contact", "owner": other_employee.pk}
    )
    assert response.status_code == 403


def test_super_admin_can_create_lead_owned_by_anyone(api_client, super_admin, other_employee):
    api_client.force_authenticate(super_admin)
    response = api_client.post(
        LEADS_URL, {"company_name": "Co", "contact_name": "Contact", "owner": other_employee.pk}
    )
    assert response.status_code == 201
    assert response.data["owner"] == other_employee.pk


# --------------------------------------------------------------------------
# Phase 3: the refusal above was only half of the fix.
#
# `resolve_owner_for_create()` is called AFTER the record has been saved, in
# every `perform_create()` that uses it:
#
#     super().perform_create(serializer)                      # writes
#     resolve_owner_for_create(self.request.user, obj.owner)  # may RAISE
#
# So the 403 the tests above assert was answered by a request that had
# ALREADY committed the row — attributed to the very user the caller was
# forbidden from naming. Verified against the running dev backend: an
# Employee POSTing a Task with `owner: <super-admin-id>` got
# "You are not allowed to assign this record to that owner." AND left a
# Task behind with `owner_id` = the Super Admin, visible in the Super
# Admin's own scoped lists.
#
# Fixed once, in the shared write mixin every one of these viewsets
# inherits — `apps.core.views.AuditStampedModelMixin.create()/update()` are
# now `@transaction.atomic`, so the refusal rolls the write back. Covered
# here across both code shapes: `data.pop("owner")` (Customer) and the
# post-save-resolve shape (Lead, Task).
# --------------------------------------------------------------------------


def test_a_refused_lead_create_leaves_no_lead_behind(api_client, employee, other_employee):
    from apps.crm.models import Lead

    api_client.force_authenticate(employee)

    response = api_client.post(
        LEADS_URL,
        {"company_name": "GhostCo", "contact_name": "Contact", "owner": other_employee.pk},
    )

    assert response.status_code == 403
    # Not `active_objects`: a soft-deleted row would still be a row.
    assert not Lead.objects.filter(company_name="GhostCo").exists()


def test_a_refused_task_create_leaves_no_task_behind(api_client, employee, super_admin):
    from apps.activities.models import Task

    api_client.force_authenticate(employee)

    response = api_client.post(
        TASKS_URL,
        {"title": "GhostTask", "priority": "MEDIUM", "status": "PENDING", "owner": super_admin.pk},
        format="json",
    )

    assert response.status_code == 403
    assert not Task.objects.filter(title="GhostTask").exists()


def test_a_refused_customer_create_leaves_no_customer_behind(
    api_client, employee, other_employee, organization
):
    from apps.crm.models import Customer

    api_client.force_authenticate(employee)

    response = api_client.post(
        CUSTOMERS_URL,
        {"organization": organization.pk, "name": "GhostCustomer", "owner": other_employee.pk},
        format="json",
    )

    assert response.status_code == 403
    assert not Customer.objects.filter(name="GhostCustomer").exists()


def test_an_allowed_create_still_commits(api_client, employee):
    """The rollback must be scoped to the FAILURE — a legitimate create
    still persists, owned by its creator.
    """
    from apps.activities.models import Task

    api_client.force_authenticate(employee)

    response = api_client.post(
        TASKS_URL, {"title": "RealTask", "priority": "MEDIUM", "status": "PENDING"}, format="json"
    )

    assert response.status_code == 201
    assert Task.objects.get(title="RealTask").owner_id == employee.pk
