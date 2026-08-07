"""CP13: shared fixtures for the catalog app's DB-dependent tests.

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
        email="catalog-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="catalog-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="catalog-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def product(db):
    from apps.catalog.models import Product

    return Product.objects.create(name="Widget", sku="WID-001", default_price="10.00")


@pytest.fixture
def service(db):
    from apps.catalog.models import Service

    return Service.objects.create(name="Consulting", code="SRV-001", default_rate="150.00")


@pytest.fixture
def pricebook(db):
    from apps.catalog.models import PriceBook

    return PriceBook.objects.create(name="Standard Pricing")
