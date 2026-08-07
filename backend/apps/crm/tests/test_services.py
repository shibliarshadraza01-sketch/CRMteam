"""CP9: tests for apps/crm/services.py — including lead-conversion logic.

Every function here reads or writes real rows, so every test requires a
database and is honestly blocked in this environment along with every
other DB-dependent test since CP2.
"""
import pytest

from apps.crm.models import ContactPerson, Customer, Lead
from apps.crm.services import (
    add_address,
    add_contact,
    assign_owner,
    convert_lead,
    create_customer,
    create_lead,
)


@pytest.mark.django_db
def test_create_customer_auto_generates_slug(organization):
    customer = create_customer(organization, "Globex Corp")
    assert customer.slug == "globex-corp"


@pytest.mark.django_db
def test_create_customer_respects_explicit_slug(organization):
    customer = create_customer(organization, "Globex Corp", slug="gx")
    assert customer.slug == "gx"


@pytest.mark.django_db
def test_create_customer_sets_owner(organization, owner):
    customer = create_customer(organization, "Globex Corp", owner=owner)
    assert customer.owner_id == owner.id


@pytest.mark.django_db
def test_create_lead_basic():
    lead = create_lead("Initech", "Peter Gibbons", email="peter@initech.com")
    assert lead.company_name == "Initech"
    assert lead.status == Lead.Status.NEW


# --------------------------------------------------------------------------
# convert_lead()
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_convert_lead_creates_customer_and_links_it(organization):
    lead = create_lead("Initech", "Peter Gibbons", email="peter@initech.com", phone="555-1234")

    customer = convert_lead(lead, organization)

    assert isinstance(customer, Customer)
    assert customer.organization_id == organization.id
    assert customer.name == "Initech"
    assert customer.email == "peter@initech.com"
    assert customer.phone == "555-1234"


@pytest.mark.django_db
def test_convert_lead_updates_lead_status_and_link(organization):
    lead = create_lead("Initech", "Peter Gibbons")

    customer = convert_lead(lead, organization)

    lead.refresh_from_db()
    assert lead.status == Lead.Status.CONVERTED
    assert lead.converted_customer_id == customer.id
    assert lead.is_converted is True


@pytest.mark.django_db
def test_convert_lead_defaults_customer_owner_to_lead_owner(organization, owner):
    lead = create_lead("Initech", "Peter Gibbons", owner=owner)

    customer = convert_lead(lead, organization)

    assert customer.owner_id == owner.id


@pytest.mark.django_db
def test_convert_lead_explicit_owner_overrides_lead_owner(organization, owner, django_user_model):
    other_owner = django_user_model.objects.create_user(email="other@example.com", password="x")
    lead = create_lead("Initech", "Peter Gibbons", owner=owner)

    customer = convert_lead(lead, organization, owner=other_owner)

    assert customer.owner_id == other_owner.id


@pytest.mark.django_db
def test_convert_lead_allows_overriding_customer_name(organization):
    lead = create_lead("initech llc", "Peter Gibbons")

    customer = convert_lead(lead, organization, name="Initech LLC")

    assert customer.name == "Initech LLC"


@pytest.mark.django_db
def test_convert_lead_twice_raises_value_error(organization):
    lead = create_lead("Initech", "Peter Gibbons")
    convert_lead(lead, organization)

    with pytest.raises(ValueError):
        convert_lead(lead, organization)


# --------------------------------------------------------------------------
# assign_owner()
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_assign_owner_sets_and_persists(customer, django_user_model):
    new_owner = django_user_model.objects.create_user(email="new-owner@example.com", password="x")

    assign_owner(customer, new_owner)
    customer.refresh_from_db()

    assert customer.owner_id == new_owner.id


@pytest.mark.django_db
def test_assign_owner_can_clear_owner(customer):
    assign_owner(customer, None)
    customer.refresh_from_db()
    assert customer.owner_id is None


@pytest.mark.django_db
def test_assign_owner_works_on_lead():
    lead = create_lead("Initech", "Peter")
    from apps.accounts.models import User

    new_owner = User.objects.create_user(email="lead-owner@example.com", password="x")

    assign_owner(lead, new_owner)
    lead.refresh_from_db()

    assert lead.owner_id == new_owner.id


# --------------------------------------------------------------------------
# add_contact()
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_add_contact_creates_a_contact(customer):
    contact = add_contact(customer, "Jane", "Doe", designation="CFO")
    assert contact.customer_id == customer.id
    assert contact.designation == "CFO"


@pytest.mark.django_db
def test_add_contact_promotes_new_primary_and_demotes_old_one(customer):
    first = add_contact(customer, "Jane", "Doe", is_primary=True)

    second = add_contact(customer, "John", "Smith", is_primary=True)

    first.refresh_from_db()
    assert first.is_primary is False
    assert second.is_primary is True
    assert ContactPerson.objects.filter(customer=customer, is_primary=True).count() == 1


@pytest.mark.django_db
def test_add_contact_non_primary_does_not_touch_existing_primary(customer):
    primary = add_contact(customer, "Jane", "Doe", is_primary=True)

    add_contact(customer, "John", "Smith", is_primary=False)

    primary.refresh_from_db()
    assert primary.is_primary is True


# --------------------------------------------------------------------------
# add_address()
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_add_address_creates_an_address(customer):
    address = add_address(customer, "BILLING", line1="1 Main St", city="Springfield", country="USA")
    assert address.customer_id == customer.id
    assert address.address_type == "BILLING"


@pytest.mark.django_db
def test_add_address_allows_multiple_addresses_of_same_type(customer):
    add_address(customer, "SHIPPING", line1="1 Main St", city="Springfield", country="USA")
    add_address(customer, "SHIPPING", line1="2 Elm St", city="Shelbyville", country="USA")
    assert customer.addresses.filter(address_type="SHIPPING").count() == 2
