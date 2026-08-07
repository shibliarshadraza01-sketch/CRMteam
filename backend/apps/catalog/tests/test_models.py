"""CP13: tests for apps/catalog/models.py."""
import pytest
from django.db import models

from apps.catalog.models import PriceBook, PriceBookEntry, Product, Service

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_product_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in Product._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_product_sku_is_unique():
    assert Product._meta.get_field("sku").unique is True


def test_product_is_active_defaults_true_and_distinct_from_is_deleted():
    assert Product._meta.get_field("is_active").default is True
    assert Product._meta.get_field("is_deleted").default is False


def test_product_default_price_is_decimal():
    assert isinstance(Product._meta.get_field("default_price"), models.DecimalField)


def test_product_str_includes_name_and_sku():
    assert str(Product(name="Widget", sku="WID-1")) == "Widget (WID-1)"


def test_service_code_is_unique():
    assert Service._meta.get_field("code").unique is True


def test_service_str_includes_name_and_code():
    assert str(Service(name="Consulting", code="SRV-1")) == "Consulting (SRV-1)"


def test_pricebook_name_is_unique():
    assert PriceBook._meta.get_field("name").unique is True


def test_pricebook_str_returns_name():
    assert str(PriceBook(name="Standard")) == "Standard"


def test_pricebookentry_fk_related_names():
    assert PriceBookEntry._meta.get_field("price_book").remote_field.related_name == "entries"
    assert PriceBookEntry._meta.get_field("product").remote_field.related_name == "pricebook_entries"
    assert PriceBookEntry._meta.get_field("service").remote_field.related_name == "pricebook_entries"


def test_pricebookentry_product_and_service_are_nullable():
    assert PriceBookEntry._meta.get_field("product").null is True
    assert PriceBookEntry._meta.get_field("service").null is True


def test_pricebookentry_has_exactly_one_constraint():
    constraint_names = {c.name for c in PriceBookEntry._meta.constraints}
    assert "catalog_entry_exactly_one_of_product_or_service" in constraint_names
    assert "catalog_entry_unique_pricebook_product" in constraint_names
    assert "catalog_entry_unique_pricebook_service" in constraint_names


def test_pricebookentry_item_property_returns_product_when_set():
    product = Product(name="Widget", sku="W1")
    entry = PriceBookEntry(product=product)
    assert entry.item is product


def test_pricebookentry_item_property_returns_service_when_set():
    service = Service(name="Consulting", code="S1")
    entry = PriceBookEntry(service=service)
    assert entry.item is service


def test_pricebookentry_str_includes_pricebook_item_and_price():
    book = PriceBook(name="Standard")
    product = Product(name="Widget", sku="W1")
    entry = PriceBookEntry(price_book=book, product=product, price="19.99")
    assert "Standard" in str(entry)
    assert "19.99" in str(entry)


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_product_create_and_retrieve():
    p = Product.objects.create(name="Widget", sku="WID-100")
    assert Product.objects.get(pk=p.pk).is_active is True


@pytest.mark.django_db
def test_product_sku_uniqueness_enforced():
    from django.db import IntegrityError

    Product.objects.create(name="A", sku="DUP")
    with pytest.raises(IntegrityError):
        Product.objects.create(name="B", sku="DUP")


@pytest.mark.django_db
def test_pricebookentry_exactly_one_constraint_rejects_both(pricebook, product, service):
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        PriceBookEntry.objects.create(price_book=pricebook, product=product, service=service, price=10)


@pytest.mark.django_db
def test_pricebookentry_exactly_one_constraint_rejects_neither(pricebook):
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        PriceBookEntry.objects.create(price_book=pricebook, price=10)


@pytest.mark.django_db
def test_pricebookentry_unique_per_pricebook_and_product(pricebook, product):
    from django.db import IntegrityError

    PriceBookEntry.objects.create(price_book=pricebook, product=product, price=10)
    with pytest.raises(IntegrityError):
        PriceBookEntry.objects.create(price_book=pricebook, product=product, price=20)


@pytest.mark.django_db
def test_pricebookentry_allows_same_product_in_different_pricebooks(pricebook, product):
    other_book = PriceBook.objects.create(name="EU Pricing")
    PriceBookEntry.objects.create(price_book=pricebook, product=product, price=10)
    # Same product, different price book — fine.
    PriceBookEntry.objects.create(price_book=other_book, product=product, price=12)


@pytest.mark.django_db
def test_deleting_product_cascades_to_entries(pricebook, product):
    entry = PriceBookEntry.objects.create(price_book=pricebook, product=product, price=10)
    product.delete()
    assert not PriceBookEntry.objects.filter(pk=entry.pk).exists()


@pytest.mark.django_db
def test_deleting_pricebook_cascades_to_entries(pricebook, product):
    entry = PriceBookEntry.objects.create(price_book=pricebook, product=product, price=10)
    pricebook.delete()
    assert not PriceBookEntry.objects.filter(pk=entry.pk).exists()
