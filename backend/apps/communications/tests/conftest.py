"""CP15: shared fixtures for the communications app's DB-dependent tests.

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
        email="comms-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="comms-employee2@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="comms-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="comms-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def organization(db):
    from apps.organization.models import Organization

    return Organization.objects.create(name="Comms Acme Inc", slug="comms-acme-inc")


@pytest.fixture
def customer(db, organization, employee):
    from apps.crm.models import Customer

    return Customer.objects.create(
        organization=organization, name="Comms Acme Customer", slug="comms-acme-customer", owner=employee
    )


@pytest.fixture
def email_template(db):
    from apps.communications.models import EmailTemplate

    return EmailTemplate.objects.create(
        name="Welcome Email", subject="Welcome, {{name}}!", body="Hi {{name}}, thanks for joining."
    )


@pytest.fixture
def email_message(db, employee):
    from apps.communications.models import EmailMessage

    return EmailMessage.objects.create(
        owner=employee, to_email="lead@example.com", subject="Hello", body="Hi there"
    )


@pytest.fixture
def notification(db, employee):
    from apps.communications.models import Notification

    return Notification.objects.create(recipient=employee, title="You have a new task")
