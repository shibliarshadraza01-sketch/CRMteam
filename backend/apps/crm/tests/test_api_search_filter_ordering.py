"""CP10: tests for search (DRF SearchFilter), filtering (django-filter),
and ordering (DRF OrderingFilter) on the CRM API. Requires a real database.
"""
import pytest

from apps.crm.models import Customer, Lead

pytestmark = pytest.mark.django_db

CUSTOMERS_URL = "/api/v1/crm/customers/"
LEADS_URL = "/api/v1/crm/leads/"


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


def test_search_customers_by_name(api_client, super_admin, organization):
    Customer.objects.create(organization=organization, name="Acme Rockets", slug="acme-rockets")
    Customer.objects.create(organization=organization, name="Globex", slug="globex")
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"search": "Rockets"})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Acme Rockets"}


def test_search_customers_by_website(api_client, super_admin, organization):
    Customer.objects.create(organization=organization, name="Acme", slug="acme", website="https://acme.example.com")
    Customer.objects.create(organization=organization, name="Globex", slug="globex", website="https://globex.example.com")
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"search": "acme.example"})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Acme"}


def test_search_leads_by_company_and_contact_name(api_client, super_admin):
    Lead.objects.create(company_name="Initech", contact_name="Peter Gibbons")
    Lead.objects.create(company_name="Hooli", contact_name="Gavin Belson")
    api_client.force_authenticate(super_admin)

    by_company = api_client.get(LEADS_URL, {"search": "Initech"})
    by_contact = api_client.get(LEADS_URL, {"search": "Belson"})

    assert {r["company_name"] for r in by_company.data["results"]} == {"Initech"}
    assert {r["company_name"] for r in by_contact.data["results"]} == {"Hooli"}


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------


def test_filter_customers_by_status(api_client, super_admin, organization):
    Customer.objects.create(organization=organization, name="A", slug="a", status=Customer.Status.ACTIVE)
    Customer.objects.create(organization=organization, name="B", slug="b", status=Customer.Status.PROSPECT)
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"status": Customer.Status.ACTIVE})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"A"}


def test_filter_customers_by_is_active(api_client, super_admin, organization):
    Customer.objects.create(organization=organization, name="Active", slug="active-c", is_active=True)
    Customer.objects.create(organization=organization, name="Inactive", slug="inactive-c", is_active=False)
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"is_active": "false"})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Inactive"}


def test_filter_customers_by_owner(api_client, super_admin, organization, employee, other_employee):
    Customer.objects.create(organization=organization, name="Mine", slug="mine", owner=employee)
    Customer.objects.create(organization=organization, name="Theirs", slug="theirs", owner=other_employee)
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"owner": employee.id})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Mine"}


def test_filter_customers_by_industry(api_client, super_admin, organization):
    Customer.objects.create(organization=organization, name="A", slug="a", industry="Retail")
    Customer.objects.create(organization=organization, name="B", slug="b", industry="Manufacturing")
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"industry": "Retail"})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"A"}


def test_filter_leads_by_source(api_client, super_admin):
    Lead.objects.create(company_name="A", contact_name="A", source=Lead.Source.WEBSITE)
    Lead.objects.create(company_name="B", contact_name="B", source=Lead.Source.REFERRAL)
    api_client.force_authenticate(super_admin)

    response = api_client.get(LEADS_URL, {"source": Lead.Source.WEBSITE})

    names = {row["company_name"] for row in response.data["results"]}
    assert names == {"A"}


def test_filter_leads_by_converted(api_client, super_admin, customer):
    converted = Lead.objects.create(company_name="A", contact_name="A", converted_customer=customer, status=Lead.Status.CONVERTED)
    unconverted = Lead.objects.create(company_name="B", contact_name="B")
    api_client.force_authenticate(super_admin)

    converted_response = api_client.get(LEADS_URL, {"converted": "true"})
    unconverted_response = api_client.get(LEADS_URL, {"converted": "false"})

    assert {r["company_name"] for r in converted_response.data["results"]} == {"A"}
    assert {r["company_name"] for r in unconverted_response.data["results"]} == {"B"}


# --------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------


def test_order_customers_by_name(api_client, super_admin, organization):
    Customer.objects.create(organization=organization, name="Zebra", slug="zebra")
    Customer.objects.create(organization=organization, name="Alpha", slug="alpha")
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"ordering": "name"})

    names = [row["name"] for row in response.data["results"]]
    assert names == ["Alpha", "Zebra"]


def test_order_customers_by_name_descending(api_client, super_admin, organization):
    Customer.objects.create(organization=organization, name="Zebra", slug="zebra")
    Customer.objects.create(organization=organization, name="Alpha", slug="alpha")
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL, {"ordering": "-name"})

    names = [row["name"] for row in response.data["results"]]
    assert names == ["Zebra", "Alpha"]


def test_order_leads_by_name_alias_maps_to_company_name(api_client, super_admin):
    Lead.objects.create(company_name="Zeta Corp", contact_name="Z")
    Lead.objects.create(company_name="Alpha Corp", contact_name="A")
    api_client.force_authenticate(super_admin)

    response = api_client.get(LEADS_URL, {"ordering": "name"})

    companies = [row["company_name"] for row in response.data["results"]]
    assert companies == ["Alpha Corp", "Zeta Corp"]
