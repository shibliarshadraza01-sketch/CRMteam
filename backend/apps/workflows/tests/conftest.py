"""CP17: shared fixtures for the workflows app's DB-dependent tests.

Every fixture here requires a real database and is therefore itself
blocked in this environment along with every other DB-dependent test
since CP2 — see BACKEND_PROGRESS.md.
"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="workflows-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="workflows-employee2@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="workflows-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="workflows-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def organization(db):
    from apps.organization.models import Organization

    return Organization.objects.create(name="Workflows Acme Inc", slug="workflows-acme-inc")


@pytest.fixture
def customer(db, organization, employee):
    from apps.crm.models import Customer

    return Customer.objects.create(
        organization=organization,
        name="Workflows Acme Customer",
        slug="workflows-acme-customer",
        owner=employee,
        email="customer@workflows-acme.example",
    )


@pytest.fixture
def lead(db, employee):
    from apps.crm.models import Lead

    return Lead.objects.create(company_name="Acme", contact_name="Jane", email="jane@acme.example", owner=employee)


@pytest.fixture
def workflow(db, employee):
    from apps.workflows.models import Workflow

    return Workflow.objects.create(name="My Workflow", owner=employee)
