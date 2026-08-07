"""CP13: tests for apps/catalog/filters.py."""
import pytest

from apps.catalog.filters import PriceBookEntryFilterSet, ProductFilterSet
from apps.catalog.models import PriceBookEntry, Product

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_product_filterset_declares_expected_fields():
    assert set(ProductFilterSet.Meta.fields) == {"is_active", "currency"}


def test_pricebookentry_filterset_declares_expected_fields():
    assert set(PriceBookEntryFilterSet.Meta.fields) == {"price_book", "product", "service", "is_active"}
    assert "price_min" in PriceBookEntryFilterSet.declared_filters
    assert "price_max" in PriceBookEntryFilterSet.declared_filters


def test_price_range_filter_builds_query_without_hitting_db():
    filterset = PriceBookEntryFilterSet(data={"price_min": "10"}, queryset=PriceBookEntry.objects.all())
    assert filterset.is_valid()
    assert len(filterset.qs.query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_price_range_filter_matches_real_rows(pricebook, product):
    from apps.catalog.services import add_pricebook_entry

    cheap = add_pricebook_entry(pricebook, 5, product=product)
    other_product = Product.objects.create(name="Other3", sku="OTH-3")
    expensive = add_pricebook_entry(pricebook, 500, product=other_product)

    filterset = PriceBookEntryFilterSet(data={"price_min": "100"}, queryset=PriceBookEntry.objects.all())

    assert list(filterset.qs) == [expensive]
