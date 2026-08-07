"""CP13: tests for CatalogItemQuerySet / PriceBookEntryQuerySet."""
import pytest

from apps.catalog.models import PriceBook, PriceBookEntry, Product, Service

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_product_active_filters_is_deleted_and_is_active_without_hitting_db():
    queryset = Product.objects.active()
    where_sql = str(queryset.query.where)
    assert "is_deleted" in where_sql
    assert "is_active" in where_sql


def test_service_and_pricebook_share_the_same_active_behavior():
    for manager in (Service.objects, PriceBook.objects):
        where_sql = str(manager.active().query.where)
        assert "is_active" in where_sql


def test_pricebookentry_for_product_and_for_service_build_filters_without_hitting_db():
    assert len(PriceBookEntry.objects.for_product(None).query.where) > 0
    assert len(PriceBookEntry.objects.for_service(None).query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_active_excludes_inactive_and_deleted_products():
    active = Product.objects.create(name="Active", sku="A1", is_active=True)
    inactive = Product.objects.create(name="Inactive", sku="A2", is_active=False)
    deleted = Product.objects.create(name="Deleted", sku="A3")
    deleted.soft_delete()

    names = set(Product.active_objects.values_list("name", flat=True))
    assert names == {"Active"}


@pytest.mark.django_db
def test_pricebookentry_for_product_matches_real_rows(pricebook, product):
    entry = PriceBookEntry.objects.create(price_book=pricebook, product=product, price=10)
    other_product = Product.objects.create(name="Other", sku="OTH-1")
    PriceBookEntry.objects.create(price_book=pricebook, product=other_product, price=5)

    result = PriceBookEntry.objects.for_product(product)

    assert list(result) == [entry]


@pytest.mark.django_db
def test_pricebookentry_active_excludes_deactivated(pricebook, product):
    active_entry = PriceBookEntry.objects.create(price_book=pricebook, product=product, price=10)
    other_product = Product.objects.create(name="Other2", sku="OTH-2")
    inactive_entry = PriceBookEntry.objects.create(price_book=pricebook, product=other_product, price=5, is_active=False)

    names = set(PriceBookEntry.active_objects.values_list("price", flat=True))
    assert names == {10}
