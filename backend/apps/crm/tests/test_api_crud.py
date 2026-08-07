"""CP10: end-to-end CRUD tests for the CRM API.

Every test here drives real HTTP requests through DRF's ``APIClient``
against real database rows — genuinely requires PostgreSQL and is honestly
blocked in this environment along with every other DB-dependent test since
CP2. Authentication uses ``force_authenticate()`` (a standard DRF test
shortcut that bypasses the JWT parsing CP3 already tests elsewhere) so
these tests focus purely on the CRUD/CP10 behavior, not re-proving CP3's
own auth mechanics.
"""
import pytest

from apps.crm.models import Address, ContactPerson, Customer, Lead

pytestmark = pytest.mark.django_db

CUSTOMERS_URL = "/api/v1/crm/customers/"
LEADS_URL = "/api/v1/crm/leads/"
CONTACTS_URL = "/api/v1/crm/contacts/"
ADDRESSES_URL = "/api/v1/crm/addresses/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------


def test_create_customer(api_client, organization, manager):
    api_client.force_authenticate(manager)

    response = api_client.post(
        CUSTOMERS_URL, {"organization": organization.id, "name": "Globex", "slug": "globex"}
    )

    assert response.status_code == 201
    assert response.data["name"] == "Globex"
    customer = Customer.objects.get(pk=response.data["id"])
    assert customer.owner_id == manager.id  # defaulted via assign_owner()
    assert customer.created_by_id == manager.id


def test_list_customers_returns_only_active_rows(api_client, super_admin, organization):
    visible = Customer.objects.create(organization=organization, name="Visible", slug="visible")
    deleted = Customer.objects.create(organization=organization, name="Deleted", slug="deleted")
    deleted.soft_delete()
    api_client.force_authenticate(super_admin)

    response = api_client.get(CUSTOMERS_URL)

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Visible"}


def test_retrieve_customer_uses_detail_serializer(api_client, customer, owner):
    api_client.force_authenticate(owner)

    response = api_client.get(_detail(CUSTOMERS_URL, customer.pk))

    assert response.status_code == 200
    assert "organization_name" in response.data
    assert "contacts" in response.data
    assert "addresses" in response.data


def test_patch_customer(api_client, customer, owner):
    api_client.force_authenticate(owner)

    response = api_client.patch(_detail(CUSTOMERS_URL, customer.pk), {"industry": "Manufacturing"})

    assert response.status_code == 200
    customer.refresh_from_db()
    assert customer.industry == "Manufacturing"
    assert customer.updated_by_id == owner.id


def test_put_customer_not_allowed(api_client, customer, owner):
    api_client.force_authenticate(owner)
    response = api_client.put(_detail(CUSTOMERS_URL, customer.pk), {"name": "New Name"})
    assert response.status_code == 405


def test_delete_customer_soft_deletes(api_client, customer, owner):
    api_client.force_authenticate(owner)

    response = api_client.delete(_detail(CUSTOMERS_URL, customer.pk))

    assert response.status_code == 204
    customer.refresh_from_db()
    assert customer.is_deleted is True
    assert Customer.objects.filter(pk=customer.pk).exists()  # not hard-deleted


def test_restore_customer(api_client, customer, owner):
    customer.soft_delete()
    api_client.force_authenticate(owner)

    response = api_client.post(f"{_detail(CUSTOMERS_URL, customer.pk)}restore/")

    assert response.status_code == 200
    customer.refresh_from_db()
    assert customer.is_deleted is False


def test_hard_delete_customer(api_client, customer, owner):
    pk = customer.pk
    api_client.force_authenticate(owner)

    response = api_client.post(f"{_detail(CUSTOMERS_URL, pk)}hard-delete/")

    assert response.status_code == 204
    assert not Customer.objects.filter(pk=pk).exists()


# --------------------------------------------------------------------------
# Leads
# --------------------------------------------------------------------------


def test_create_lead_defaults_owner_to_requesting_user(api_client, employee):
    api_client.force_authenticate(employee)

    response = api_client.post(LEADS_URL, {"company_name": "Initech", "contact_name": "Peter"})

    assert response.status_code == 201
    lead = Lead.objects.get(pk=response.data["id"])
    assert lead.owner_id == employee.id


def test_retrieve_lead_uses_detail_serializer(api_client, employee):
    lead = Lead.objects.create(company_name="Initech", contact_name="Peter", owner=employee)
    api_client.force_authenticate(employee)

    response = api_client.get(_detail(LEADS_URL, lead.pk))

    assert isinstance(response.data["owner"], dict)
    assert response.data["owner"]["email"] == employee.email


def test_patch_lead(api_client, employee):
    lead = Lead.objects.create(company_name="Initech", contact_name="Peter", owner=employee)
    api_client.force_authenticate(employee)

    response = api_client.patch(_detail(LEADS_URL, lead.pk), {"status": Lead.Status.QUALIFIED})

    assert response.status_code == 200
    lead.refresh_from_db()
    assert lead.status == Lead.Status.QUALIFIED


def test_delete_lead_soft_deletes(api_client, employee):
    lead = Lead.objects.create(company_name="Initech", contact_name="Peter", owner=employee)
    api_client.force_authenticate(employee)

    response = api_client.delete(_detail(LEADS_URL, lead.pk))

    assert response.status_code == 204
    lead.refresh_from_db()
    assert lead.is_deleted is True


# --------------------------------------------------------------------------
# Contacts
# --------------------------------------------------------------------------


def test_create_contact_via_service_layer(api_client, customer, owner):
    api_client.force_authenticate(owner)
    api_client.post(CONTACTS_URL, {"customer": customer.pk, "first_name": "Jane", "last_name": "Doe", "is_primary": True})

    response = api_client.post(
        CONTACTS_URL, {"customer": customer.pk, "first_name": "John", "last_name": "Smith", "is_primary": True}
    )

    assert response.status_code == 201
    # add_contact() demoted Jane before promoting John (CP9 service reuse).
    jane = ContactPerson.objects.get(first_name="Jane")
    assert jane.is_primary is False


def test_create_second_primary_contact_rejected_by_serializer_validation(api_client, customer, owner):
    ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe", is_primary=True)
    api_client.force_authenticate(owner)

    # Directly via serializer validation path (not add_contact()'s
    # auto-demote) — PATCH on an existing non-primary contact trying to
    # become primary while another primary already exists should still be
    # rejected by ContactPersonSerializer.validate() on update.
    other = ContactPerson.objects.create(customer=customer, first_name="John", last_name="Smith", is_primary=False)
    response = api_client.patch(_detail(CONTACTS_URL, other.pk), {"is_primary": True})

    assert response.status_code == 400
    assert "is_primary" in response.data


def test_patch_contact(api_client, customer, owner):
    contact = ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe")
    api_client.force_authenticate(owner)

    response = api_client.patch(_detail(CONTACTS_URL, contact.pk), {"designation": "CFO"})

    assert response.status_code == 200
    contact.refresh_from_db()
    assert contact.designation == "CFO"


def test_delete_contact_soft_deletes(api_client, customer, owner):
    contact = ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe")
    api_client.force_authenticate(owner)

    response = api_client.delete(_detail(CONTACTS_URL, contact.pk))

    assert response.status_code == 204
    contact.refresh_from_db()
    assert contact.is_deleted is True


# --------------------------------------------------------------------------
# Addresses
# --------------------------------------------------------------------------


def test_create_address(api_client, customer, owner):
    api_client.force_authenticate(owner)

    response = api_client.post(
        ADDRESSES_URL,
        {"customer": customer.pk, "address_type": "BILLING", "line1": "1 Main St", "city": "Springfield", "country": "USA"},
    )

    assert response.status_code == 201
    assert Address.objects.filter(customer=customer, address_type="BILLING").exists()


def test_patch_address(api_client, customer, owner):
    address = Address.objects.create(customer=customer, address_type="BILLING", line1="1 Main St", city="Springfield", country="USA")
    api_client.force_authenticate(owner)

    response = api_client.patch(_detail(ADDRESSES_URL, address.pk), {"city": "Shelbyville"})

    assert response.status_code == 200
    address.refresh_from_db()
    assert address.city == "Shelbyville"


def test_delete_address_soft_deletes(api_client, customer, owner):
    address = Address.objects.create(customer=customer, address_type="BILLING", line1="1 Main St", city="Springfield", country="USA")
    api_client.force_authenticate(owner)

    response = api_client.delete(_detail(ADDRESSES_URL, address.pk))

    assert response.status_code == 204
    address.refresh_from_db()
    assert address.is_deleted is True
