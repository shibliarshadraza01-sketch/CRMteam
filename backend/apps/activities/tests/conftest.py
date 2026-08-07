"""CP14: shared fixtures for the activities app's DB-dependent tests.

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
        email="activities-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="activities-employee2@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="activities-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="activities-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def organization(db):
    from apps.organization.models import Organization

    return Organization.objects.create(name="Acme Inc", slug="acme-inc")


@pytest.fixture
def customer(db, organization, employee):
    from apps.crm.models import Customer

    return Customer.objects.create(organization=organization, name="Acme Customer", slug="acme-customer", owner=employee)


@pytest.fixture
def task(db, employee):
    from apps.activities.models import Task

    return Task.objects.create(title="Follow up", owner=employee)


@pytest.fixture
def event(db, employee):
    from apps.activities.models import Event
    from django.utils import timezone

    return Event.objects.create(title="Kickoff call", owner=employee, start_at=timezone.now())
