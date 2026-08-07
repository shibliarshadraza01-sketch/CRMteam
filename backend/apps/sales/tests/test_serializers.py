"""CP12: tests for apps/sales/serializers.py."""
import pytest
from rest_framework import serializers

from apps.sales.serializers import (
    InvoiceDetailSerializer,
    InvoiceItemSerializer,
    InvoiceSerializer,
    QuoteDetailSerializer,
    QuoteItemSerializer,
    QuoteSerializer,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_quote_serializer_fields():
    fields = QuoteSerializer().fields
    assert {
        "id", "customer", "opportunity", "owner", "quote_number", "status", "valid_until",
        "subtotal", "tax", "total", "notes", "approved_by", "approved_at", "converted_invoice",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_quote_serializer_workflow_fields_are_read_only():
    fields = QuoteSerializer().fields
    for name in ("status", "subtotal", "total", "approved_by", "approved_at", "converted_invoice"):
        assert fields[name].read_only is True, f"{name} should be read-only"


def test_quote_serializer_business_fields_are_writable():
    fields = QuoteSerializer().fields
    for name in ("customer", "opportunity", "owner", "quote_number", "valid_until", "tax", "notes"):
        assert fields[name].read_only is False, f"{name} should be writable"


def test_quote_detail_serializer_nests_owner_approver_customer_name_items():
    fields = QuoteDetailSerializer().fields
    assert isinstance(fields["owner"], serializers.Serializer)
    assert isinstance(fields["approved_by"], serializers.Serializer)
    assert isinstance(fields["converted_invoice"], serializers.Serializer)
    assert "customer_name" in fields
    assert isinstance(fields["items"], serializers.ListSerializer)


def test_quote_detail_serializer_is_entirely_read_only():
    for name, field in QuoteDetailSerializer().fields.items():
        assert field.read_only is True, f"{name} should be read-only"


def test_invoice_serializer_fields():
    fields = InvoiceSerializer().fields
    assert {
        "id", "customer", "quote", "owner", "invoice_number", "status", "due_date",
        "subtotal", "tax", "total", "paid_at",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_invoice_serializer_workflow_fields_are_read_only():
    fields = InvoiceSerializer().fields
    for name in ("status", "subtotal", "total", "paid_at"):
        assert fields[name].read_only is True


def test_invoice_detail_serializer_nests_owner_customer_name_quote_items():
    fields = InvoiceDetailSerializer().fields
    assert isinstance(fields["owner"], serializers.Serializer)
    assert "customer_name" in fields
    assert isinstance(fields["quote"], serializers.Serializer)
    assert isinstance(fields["items"], serializers.ListSerializer)


def test_invoice_detail_serializer_is_entirely_read_only():
    for name, field in InvoiceDetailSerializer().fields.items():
        assert field.read_only is True, f"{name} should be read-only"


def test_quote_item_serializer_total_price_is_read_only():
    field = QuoteItemSerializer().fields["total_price"]
    assert field.read_only is True


def test_invoice_item_serializer_total_price_is_read_only():
    field = InvoiceItemSerializer().fields["total_price"]
    assert field.read_only is True


def test_quote_item_serializer_business_fields_writable():
    fields = QuoteItemSerializer().fields
    for name in ("quote", "product_name", "quantity", "unit_price", "ordering"):
        assert fields[name].read_only is False


# --------------------------------------------------------------------------
# Requires database — full validation (FK fields query the database)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_quote_serializer_accepts_valid_input(customer):
    serializer = QuoteSerializer(data={"customer": customer.pk, "quote_number": "Q-VALID"})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_quote_detail_serializer_output(quote, owner):
    from apps.sales.services import add_quote_item

    add_quote_item(quote, "Widget", 1, 10)

    data = QuoteDetailSerializer(quote).data

    assert data["owner"]["email"] == owner.email
    assert data["customer_name"] == quote.customer.name
    assert len(data["items"]) == 1
