"""CP12: shared fixtures for the sales app's DB-dependent tests.

Every fixture here requires a real database and is therefore itself
blocked in this environment along with every other DB-dependent test
since CP2 — see BACKEND_PROGRESS.md.
"""
import pytest
from rest_framework.test import APIClient

from apps.crm.models import Customer
from apps.organization.models import Organization


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="Acme Inc", slug="acme-inc-sales")


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        email="sales-owner@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="sales-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="sales-other-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="sales-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="sales-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def managed_team(db, organization, manager, employee):
    from apps.organization.models import Department, Membership, Team

    department = Department.objects.create(organization=organization, name="Sales Dept")
    team = Team.objects.create(department=department, name="Sales Team", manager=manager)
    Membership.objects.create(user=employee, team=team)
    return team


@pytest.fixture
def customer(db, organization, owner):
    return Customer.objects.create(organization=organization, name="Globex Corp", slug="globex-corp-sales", owner=owner)


@pytest.fixture
def quote(db, customer, owner):
    from apps.sales.models import Quote

    return Quote.objects.create(customer=customer, quote_number="Q-0001", owner=owner)


@pytest.fixture
def approved_quote(db, quote, super_admin):
    from apps.sales.services import approve_quote, submit_quote

    submit_quote(quote)
    approve_quote(quote, super_admin)
    quote.refresh_from_db()
    return quote


@pytest.fixture
def invoice(db, customer, owner):
    from apps.sales.models import Invoice

    return Invoice.objects.create(customer=customer, invoice_number="INV-0001", owner=owner)
