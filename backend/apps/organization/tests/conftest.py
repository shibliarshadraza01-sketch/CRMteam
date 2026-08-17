"""Shared fixtures for the organization app's DB-dependent API tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="org-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="org-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="org-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def organization(db):
    from apps.organization.models import Organization

    return Organization.objects.create(name="Acme Inc", slug="acme-inc")


@pytest.fixture
def department(db, organization):
    from apps.organization.models import Department

    return Department.objects.create(organization=organization, name="Sales")


@pytest.fixture
def team(db, department, manager):
    from apps.organization.models import Team

    return Team.objects.create(department=department, name="Enterprise Sales", manager=manager)
