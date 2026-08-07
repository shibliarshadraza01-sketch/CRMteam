"""CP9/CP10: shared fixtures for the crm app's DB-dependent tests.

Every fixture here requires a real database (creating an ``Organization``/
``Customer`` is a persistence operation) and is therefore itself blocked in
this environment along with every other DB-dependent test since CP2 — see
BACKEND_PROGRESS.md.
"""
import pytest
from rest_framework.test import APIClient

from apps.organization.models import Organization


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Acme Inc", slug="acme-inc")


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        email="owner@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def customer(db, organization, owner):
    from apps.crm.models import Customer

    return Customer.objects.create(organization=organization, name="Globex Corp", slug="globex-corp", owner=owner)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="other-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def managed_team(db, organization, manager, employee):
    """A CP8 ``Team`` managed by ``manager`` with ``employee`` as a member —
    the setup CP10's "Managers see their team's records" rule needs.
    """
    from apps.organization.models import Department, Membership, Team

    department = Department.objects.create(organization=organization, name="Sales")
    team = Team.objects.create(department=department, name="Alpha", manager=manager)
    Membership.objects.create(user=employee, team=team)
    return team


@pytest.fixture
def opportunity(db, customer, owner):
    from apps.crm.opportunities import Opportunity

    return Opportunity.objects.create(customer=customer, title="Big Deal", owner=owner, value="15000.00")
