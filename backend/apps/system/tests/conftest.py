"""CP19: shared fixtures for the system app's DB-dependent tests.

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
        email="system-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="system-employee2@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="system-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="system-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def organization(db):
    from apps.organization.models import Organization

    return Organization.objects.create(name="System Acme Inc", slug="system-acme-inc")


@pytest.fixture
def customer(db, organization, employee):
    from apps.crm.models import Customer

    return Customer.objects.create(
        organization=organization, name="System Acme Customer", slug="system-acme-customer", owner=employee
    )


@pytest.fixture
def setting(db):
    from apps.system.models import SystemSetting

    return SystemSetting.objects.create(key="max_upload_size_mb", value=25)


@pytest.fixture
def flag(db):
    from apps.system.models import FeatureFlag

    return FeatureFlag.objects.create(key="new_dashboard", name="New Dashboard", is_enabled=True)


@pytest.fixture
def job(db, employee):
    from apps.system.models import BackgroundJob

    return BackgroundJob.objects.create(name="Export leads", job_type="EXPORT", owner=employee)
