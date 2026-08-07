"""CP16: shared fixtures for the reports app's DB-dependent tests.

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
        email="reports-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="reports-employee2@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="reports-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="reports-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def organization(db):
    from apps.organization.models import Organization

    return Organization.objects.create(name="Reports Acme Inc", slug="reports-acme-inc")


@pytest.fixture
def customer(db, organization, employee):
    from apps.crm.models import Customer

    return Customer.objects.create(
        organization=organization, name="Reports Acme Customer", slug="reports-acme-customer", owner=employee
    )


@pytest.fixture
def saved_report(db, employee):
    from apps.reports.models import SavedReport

    return SavedReport.objects.create(
        name="My Productivity", report_type=SavedReport.ReportType.PRODUCTIVITY, owner=employee
    )


@pytest.fixture
def dashboard(db, employee):
    from apps.reports.models import Dashboard

    return Dashboard.objects.create(name="My Dashboard", owner=employee)
