"""CP9: tests for apps/crm/models.py.

Split, following the CP4-CP8 pattern, into DB-free tests (field
definitions, Meta options, pure-Python properties operating on in-memory
instances) and DB-dependent tests (persistence, constraints, cascade
behavior against real rows) — the latter honestly blocked by the same
missing-PostgreSQL issue as every DB-backed test since CP2.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models

from apps.crm.models import Address, ContactPerson, Customer, Lead
from apps.organization.models import Organization

User = get_user_model()


def _unsaved_user(role=User.Role.EMPLOYEE, email="user@example.com"):
    return User(email=email, role=role)


# --------------------------------------------------------------------------
# No database required — field/Meta definitions
# --------------------------------------------------------------------------


def test_customer_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in Customer._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_customer_fk_related_names():
    org_field = Customer._meta.get_field("organization")
    owner_field = Customer._meta.get_field("owner")
    assert org_field.remote_field.related_name == "customers"
    assert org_field.remote_field.on_delete is models.CASCADE
    assert owner_field.remote_field.related_name == "owned_customers"
    assert owner_field.remote_field.on_delete is models.SET_NULL
    assert owner_field.null is True


def test_customer_unique_constraint_on_organization_and_slug():
    constraint_names = {c.name for c in Customer._meta.constraints}
    assert "crm_customer_unique_org_slug" in constraint_names


def test_customer_status_default_is_prospect():
    assert Customer._meta.get_field("status").default == Customer.Status.PROSPECT


def test_customer_is_active_defaults_true_and_is_distinct_from_is_deleted():
    is_active = Customer._meta.get_field("is_active")
    is_deleted = Customer._meta.get_field("is_deleted")
    assert is_active.default is True
    assert is_deleted.default is False
    assert is_active.name != is_deleted.name


def test_customer_str():
    customer = Customer(name="Globex Corp")
    assert str(customer) == "Globex Corp"


def test_lead_fk_related_names():
    owner_field = Lead._meta.get_field("owner")
    converted_field = Lead._meta.get_field("converted_customer")
    assert owner_field.remote_field.related_name == "owned_leads"
    assert converted_field.remote_field.related_name == "converted_from_leads"
    assert converted_field.remote_field.on_delete is models.SET_NULL
    assert converted_field.null is True


def test_lead_status_default_is_new():
    assert Lead._meta.get_field("status").default == Lead.Status.NEW


def test_lead_str():
    lead = Lead(company_name="Initech", contact_name="Peter Gibbons")
    assert str(lead) == "Initech (Peter Gibbons)"


def test_lead_is_converted_false_without_converted_customer():
    lead = Lead(company_name="Initech", contact_name="Peter")
    assert lead.is_converted is False


def test_lead_is_converted_true_with_converted_customer():
    lead = Lead(company_name="Initech", contact_name="Peter")
    customer = Customer(name="Initech")
    customer.pk = 1
    lead.converted_customer = customer
    assert lead.is_converted is True


# --------------------------------------------------------------------------
# External-ingestion readiness (Phase 6 audit): external_source_id /
# source_metadata / received_at.
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_lead_external_source_id_defaults_blank_and_is_optional():
    lead = Lead.objects.create(company_name="Acme", contact_name="Jane")
    assert lead.external_source_id == ""
    assert lead.source_metadata == {}
    assert lead.received_at is None


@pytest.mark.django_db
def test_two_leads_may_both_have_a_blank_external_source_id():
    """The unique constraint is scoped to NON-blank values — every lead
    entered directly or via the existing import leaves this blank, and a
    second (or hundredth) one must not collide.
    """
    Lead.objects.create(company_name="Acme", contact_name="Jane")
    Lead.objects.create(company_name="Beta", contact_name="Bob")
    assert Lead.objects.count() == 2


@pytest.mark.django_db
def test_duplicate_external_source_id_is_rejected():
    Lead.objects.create(company_name="Acme", contact_name="Jane", external_source_id="fb-lead-123")
    with pytest.raises(IntegrityError):
        Lead.objects.create(company_name="Beta", contact_name="Bob", external_source_id="fb-lead-123")


@pytest.mark.django_db
def test_lead_source_metadata_stores_arbitrary_campaign_info():
    lead = Lead.objects.create(
        company_name="Acme",
        contact_name="Jane",
        source_metadata={"campaign": "Spring Sale", "utm_source": "facebook", "ad_id": "998877"},
    )
    lead.refresh_from_db()
    assert lead.source_metadata == {"campaign": "Spring Sale", "utm_source": "facebook", "ad_id": "998877"}


def test_contactperson_fk_related_name():
    field = ContactPerson._meta.get_field("customer")
    assert field.remote_field.related_name == "contacts"
    assert field.remote_field.on_delete is models.CASCADE


def test_contactperson_primary_partial_unique_constraint():
    constraint_names = {c.name for c in ContactPerson._meta.constraints}
    assert "crm_contactperson_unique_primary_per_customer" in constraint_names
    constraint = next(
        c for c in ContactPerson._meta.constraints if c.name == "crm_contactperson_unique_primary_per_customer"
    )
    assert constraint.condition == models.Q(is_primary=True)


def test_contactperson_full_name_property():
    contact = ContactPerson(first_name="Jane", last_name="Doe")
    assert contact.full_name == "Jane Doe"
    assert str(contact) == "Jane Doe"


def test_contactperson_owner_property_delegates_to_customer():
    owner = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    customer = Customer(name="Globex")
    customer.owner = owner
    contact = ContactPerson(customer=customer, first_name="Jane", last_name="Doe")
    assert contact.owner is owner


def test_address_fk_related_name():
    field = Address._meta.get_field("customer")
    assert field.remote_field.related_name == "addresses"
    assert field.remote_field.on_delete is models.CASCADE


def test_address_str_includes_type_and_city():
    address = Address(address_type=Address.AddressType.BILLING, line1="1 Main St", city="Springfield")
    assert "Billing" in str(address)
    assert "Springfield" in str(address)


def test_address_owner_property_delegates_to_customer():
    owner = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    customer = Customer(name="Globex")
    customer.owner = owner
    address = Address(customer=customer, line1="1 Main St", city="Springfield", country="USA")
    assert address.owner is owner


# --------------------------------------------------------------------------
# Requires database — persistence, constraints, cascades
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_customer_create_and_retrieve(organization, owner):
    customer = Customer.objects.create(organization=organization, name="Globex", slug="globex", owner=owner)
    fetched = Customer.objects.get(pk=customer.pk)
    assert fetched.name == "Globex"
    assert fetched.owner_id == owner.id


@pytest.mark.django_db
def test_customer_slug_unique_per_organization(organization):
    Customer.objects.create(organization=organization, name="Globex", slug="globex")
    with pytest.raises(IntegrityError):
        Customer.objects.create(organization=organization, name="Globex 2", slug="globex")


@pytest.mark.django_db
def test_customer_slug_can_repeat_across_organizations(organization):
    other_org = Organization.objects.create(name="Beta Co", slug="beta-co")
    Customer.objects.create(organization=organization, name="Globex", slug="globex")
    # Same slug, different organization — fine.
    Customer.objects.create(organization=other_org, name="Globex", slug="globex")


@pytest.mark.django_db
def test_deleting_organization_cascades_to_customers(organization):
    customer = Customer.objects.create(organization=organization, name="Globex", slug="globex")
    organization.delete()
    assert not Customer.objects.filter(pk=customer.pk).exists()


@pytest.mark.django_db
def test_deleting_owner_sets_null_not_cascade(organization, owner):
    customer = Customer.objects.create(organization=organization, name="Globex", slug="globex", owner=owner)
    owner.delete()
    customer.refresh_from_db()
    assert customer.owner_id is None


@pytest.mark.django_db
def test_contactperson_primary_constraint_rejects_second_primary(customer):
    ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe", is_primary=True)
    with pytest.raises(IntegrityError):
        ContactPerson.objects.create(customer=customer, first_name="John", last_name="Smith", is_primary=True)


@pytest.mark.django_db
def test_contactperson_allows_multiple_non_primary_contacts(customer):
    ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe", is_primary=False)
    ContactPerson.objects.create(customer=customer, first_name="John", last_name="Smith", is_primary=False)
    assert customer.contacts.count() == 2


@pytest.mark.django_db
def test_deleting_customer_cascades_to_contacts_and_addresses(customer):
    contact = ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe")
    address = Address.objects.create(customer=customer, address_type=Address.AddressType.BILLING, line1="1 Main St", city="Springfield", country="USA")

    customer.delete()

    assert not ContactPerson.objects.filter(pk=contact.pk).exists()
    assert not Address.objects.filter(pk=address.pk).exists()


@pytest.mark.django_db
def test_reverse_relationships_traverse_customer_to_children(customer):
    ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe")
    Address.objects.create(customer=customer, address_type=Address.AddressType.SHIPPING, line1="2 Elm St", city="Shelbyville", country="USA")

    assert customer.contacts.count() == 1
    assert customer.addresses.count() == 1


@pytest.mark.django_db
def test_lead_convert_link_persists(customer):
    lead = Lead.objects.create(company_name="Initech", contact_name="Peter", converted_customer=customer, status=Lead.Status.CONVERTED)
    lead.refresh_from_db()
    assert lead.converted_customer_id == customer.pk
    assert lead.is_converted is True
    assert customer.converted_from_leads.count() == 1


@pytest.mark.django_db
def test_deleting_converted_customer_sets_lead_link_null(customer):
    lead = Lead.objects.create(company_name="Initech", contact_name="Peter", converted_customer=customer, status=Lead.Status.CONVERTED)
    customer.delete()
    lead.refresh_from_db()
    assert lead.converted_customer_id is None
