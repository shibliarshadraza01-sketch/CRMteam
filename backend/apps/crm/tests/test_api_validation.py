"""CP10: tests confirming CP9's serializer validation rules are enforced
through the real HTTP layer, not just at the serializer unit-test level
(see apps/crm/tests/test_serializers.py, CP9, for the DB-free equivalents).
Requires a real database.
"""
import pytest

from apps.crm.models import Lead

pytestmark = pytest.mark.django_db

LEADS_URL = "/api/v1/crm/leads/"
CUSTOMERS_URL = "/api/v1/crm/customers/"


def test_creating_lead_with_converted_status_is_rejected(api_client, employee):
    api_client.force_authenticate(employee)

    response = api_client.post(
        LEADS_URL, {"company_name": "A", "contact_name": "A", "status": Lead.Status.CONVERTED}
    )

    assert response.status_code == 400
    assert "status" in response.data


def test_creating_customer_without_required_field_is_rejected(api_client, employee, organization):
    api_client.force_authenticate(employee)

    response = api_client.post(CUSTOMERS_URL, {"organization": organization.id, "name": "Acme"})  # missing slug

    assert response.status_code == 400
    assert "slug" in response.data


def test_creating_customer_with_duplicate_slug_in_same_organization_is_rejected(api_client, employee, organization):
    from apps.crm.models import Customer

    Customer.objects.create(organization=organization, name="Acme", slug="acme")
    api_client.force_authenticate(employee)

    response = api_client.post(CUSTOMERS_URL, {"organization": organization.id, "name": "Acme 2", "slug": "acme"})

    assert response.status_code == 400
