"""CP13: tests for apps/catalog/serializers.py."""
import pytest
from rest_framework import serializers

from apps.catalog.serializers import (
    PriceBookDetailSerializer,
    PriceBookEntryDetailSerializer,
    PriceBookEntrySerializer,
    PriceBookSerializer,
    ProductSerializer,
    ServiceSerializer,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_product_serializer_fields():
    fields = ProductSerializer().fields
    assert {
        "id", "name", "sku", "description", "default_price", "currency", "is_active",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_service_serializer_fields():
    fields = ServiceSerializer().fields
    assert {
        "id", "name", "code", "description", "default_rate", "currency", "is_active",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_pricebook_serializer_fields():
    fields = PriceBookSerializer().fields
    assert {
        "id", "name", "description", "currency", "is_active",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_pricebook_detail_serializer_nests_entries():
    fields = PriceBookDetailSerializer().fields
    assert isinstance(fields["entries"], serializers.ListSerializer)


def test_pricebook_detail_serializer_is_entirely_read_only():
    for name, field in PriceBookDetailSerializer().fields.items():
        assert field.read_only is True


def test_pricebookentry_serializer_business_fields_writable():
    fields = PriceBookEntrySerializer().fields
    for name in ("price_book", "product", "service", "price", "is_active"):
        assert fields[name].read_only is False


def test_pricebookentry_serializer_rejects_both_product_and_service():
    serializer = PriceBookEntrySerializer()
    with pytest.raises(serializers.ValidationError):
        serializer.validate({"product": object(), "service": object()})


def test_pricebookentry_serializer_rejects_neither():
    serializer = PriceBookEntrySerializer()
    with pytest.raises(serializers.ValidationError):
        serializer.validate({"product": None, "service": None})


def test_pricebookentry_serializer_accepts_product_only():
    serializer = PriceBookEntrySerializer()
    attrs = {"product": object(), "service": None}
    assert serializer.validate(attrs) == attrs


def test_pricebookentry_detail_serializer_nests_product_and_service():
    fields = PriceBookEntryDetailSerializer().fields
    assert isinstance(fields["product"], serializers.Serializer)
    assert isinstance(fields["service"], serializers.Serializer)
    assert "price_book_name" in fields


def test_pricebookentry_detail_serializer_is_entirely_read_only():
    for name, field in PriceBookEntryDetailSerializer().fields.items():
        assert field.read_only is True


# --------------------------------------------------------------------------
# Requires database — full serializer validation (FK fields query the DB)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_pricebookentry_serializer_full_validation_accepts_product_only(pricebook, product):
    serializer = PriceBookEntrySerializer(data={"price_book": pricebook.pk, "product": product.pk, "price": "10.00"})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_pricebook_detail_serializer_output(pricebook, product):
    from apps.catalog.services import add_pricebook_entry

    add_pricebook_entry(pricebook, 10, product=product)

    data = PriceBookDetailSerializer(pricebook).data

    assert len(data["entries"]) == 1
    assert data["entries"][0]["product"]["sku"] == product.sku
