"""CP18: shared fixtures for the integrations app's DB-dependent tests.

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
        email="integrations-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="integrations-employee2@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="integrations-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="integrations-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def organization(db):
    from apps.organization.models import Organization

    return Organization.objects.create(name="Integrations Acme Inc", slug="integrations-acme-inc")


@pytest.fixture
def integration(db, employee):
    from apps.integrations.models import Integration

    return Integration.objects.create(name="Zapier", owner=employee)


@pytest.fixture
def api_key(db, integration):
    from apps.integrations.services import generate_api_key

    key, _raw = generate_api_key(integration, "Production key")
    return key


@pytest.fixture
def webhook_endpoint(db, integration):
    from apps.integrations.services import create_webhook_endpoint

    return create_webhook_endpoint(integration, "https://example.com/hooks")
