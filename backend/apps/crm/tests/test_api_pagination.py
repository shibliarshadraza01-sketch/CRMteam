"""CP10: tests for project-wide pagination applied to the CRM API.
Requires a real database (needs real rows to paginate through).
"""
import pytest

from apps.crm.models import Customer

pytestmark = pytest.mark.django_db

CUSTOMERS_URL = "/api/v1/crm/customers/"


def _make_customers(organization, count):
    for i in range(count):
        Customer.objects.create(organization=organization, name=f"Customer {i:03d}", slug=f"customer-{i:03d}")


def test_default_page_size_is_20(api_client, super_admin, organization):
    _make_customers(organization, 25)
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL)

    assert len(response.data["results"]) == 20
    assert response.data["count"] == 25
    assert response.data["next"] is not None


def test_page_size_can_be_overridden(api_client, super_admin, organization):
    _make_customers(organization, 25)
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"page_size": 5})

    assert len(response.data["results"]) == 5


def test_page_size_cannot_exceed_max_page_size(api_client, super_admin, organization):
    _make_customers(organization, 150)
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"page_size": 500})

    assert len(response.data["results"]) == 100  # clamped to max_page_size
