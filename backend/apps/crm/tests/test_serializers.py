"""CP9: tests for apps/crm/serializers.py."""
import pytest
from rest_framework import serializers

from apps.crm.models import Address, ContactPerson, Customer, Lead
from apps.crm.serializers import (
    AddressSerializer,
    ContactPersonSerializer,
    CustomerDetailSerializer,
    CustomerSerializer,
    LeadDetailSerializer,
    LeadSerializer,
)

# --------------------------------------------------------------------------
# No database required — field declarations
# --------------------------------------------------------------------------


def test_customer_serializer_fields():
    fields = CustomerSerializer().fields
    assert {
        "id", "organization", "name", "slug", "owner", "status", "industry", "website",
        "email", "phone", "notes", "is_active",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_customer_serializer_soft_delete_and_audit_fields_read_only():
    fields = CustomerSerializer().fields
    for name in ("created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"):
        assert fields[name].read_only is True


def test_customer_detail_serializer_nests_owner_and_children():
    fields = CustomerDetailSerializer().fields
    assert isinstance(fields["owner"], serializers.Serializer)
    assert fields["owner"].read_only is True
    assert isinstance(fields["contacts"], serializers.ListSerializer)
    assert isinstance(fields["addresses"], serializers.ListSerializer)
    assert "organization_name" in fields


def test_customer_detail_serializer_is_entirely_read_only():
    for name, field in CustomerDetailSerializer().fields.items():
        assert field.read_only is True, f"{name} should be read-only"


def test_lead_serializer_converted_customer_is_read_only():
    field = LeadSerializer().fields["converted_customer"]
    assert field.read_only is True


def test_lead_serializer_rejects_converted_status_directly():
    serializer = LeadSerializer(data={"company_name": "A", "contact_name": "B", "status": Lead.Status.CONVERTED})
    assert serializer.is_valid() is False
    assert "status" in serializer.errors


def test_lead_serializer_accepts_non_converted_status():
    serializer = LeadSerializer(data={"company_name": "A", "contact_name": "B", "status": Lead.Status.QUALIFIED})
    assert serializer.is_valid(), serializer.errors


def test_lead_detail_serializer_nests_owner_and_converted_customer():
    fields = LeadDetailSerializer().fields
    assert isinstance(fields["owner"], serializers.Serializer)
    assert isinstance(fields["converted_customer"], serializers.Serializer)


def test_contactperson_serializer_fields():
    fields = ContactPersonSerializer().fields
    assert {"customer", "first_name", "last_name", "designation", "email", "phone", "is_primary"} <= set(fields.keys())


def test_address_serializer_fields():
    fields = AddressSerializer().fields
    assert {"customer", "address_type", "line1", "line2", "city", "state", "country", "postal_code"} <= set(fields.keys())


# --------------------------------------------------------------------------
# Requires database — validation logic that queries existing rows
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_contactperson_serializer_rejects_second_primary_contact(customer):
    ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe", is_primary=True)

    serializer = ContactPersonSerializer(
        data={"customer": customer.pk, "first_name": "John", "last_name": "Smith", "is_primary": True}
    )

    assert serializer.is_valid() is False
    assert "is_primary" in serializer.errors


@pytest.mark.django_db
def test_contactperson_serializer_allows_updating_the_existing_primary(customer):
    contact = ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe", is_primary=True)

    serializer = ContactPersonSerializer(
        instance=contact,
        data={"customer": customer.pk, "first_name": "Jane", "last_name": "Doe", "is_primary": True},
    )

    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_contactperson_serializer_allows_a_second_non_primary_contact(customer):
    ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe", is_primary=True)

    serializer = ContactPersonSerializer(
        data={"customer": customer.pk, "first_name": "John", "last_name": "Smith", "is_primary": False}
    )

    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_customer_detail_serializer_output_includes_nested_data(customer, owner):
    ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe", is_primary=True)
    Address.objects.create(customer=customer, address_type=Address.AddressType.BILLING, line1="1 Main St", city="Springfield", country="USA")

    data = CustomerDetailSerializer(customer).data

    assert data["owner"]["email"] == owner.email
    assert len(data["contacts"]) == 1
    assert len(data["addresses"]) == 1
    assert data["organization_name"] == customer.organization.name
