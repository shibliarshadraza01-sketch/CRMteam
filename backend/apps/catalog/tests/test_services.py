"""CP13: tests for apps/catalog/services.py. Every test requires a real
database.
"""
import pytest

from apps.catalog.models import PriceBookEntry
from apps.catalog.services import (
    add_pricebook_entry,
    create_pricebook,
    create_product,
    create_service,
    deactivate_pricebook_entry,
    update_pricebook_price,
)

pytestmark = pytest.mark.django_db


def test_create_product_basic():
    p = create_product("Widget", "WID-S1", default_price=25)
    assert p.sku == "WID-S1"
    assert p.default_price == 25


def test_create_service_basic():
    s = create_service("Consulting", "SRV-S1", default_rate=100)
    assert s.code == "SRV-S1"


def test_create_pricebook_basic():
    book = create_pricebook("Standard", currency="EUR")
    assert book.currency == "EUR"


def test_add_pricebook_entry_with_product(pricebook, product):
    entry = add_pricebook_entry(pricebook, 15, product=product)
    assert entry.product_id == product.id
    assert entry.service_id is None


def test_add_pricebook_entry_with_service(pricebook, service):
    entry = add_pricebook_entry(pricebook, 200, service=service)
    assert entry.service_id == service.id
    assert entry.product_id is None


def test_add_pricebook_entry_rejects_both(pricebook, product, service):
    with pytest.raises(ValueError):
        add_pricebook_entry(pricebook, 10, product=product, service=service)


def test_add_pricebook_entry_rejects_neither(pricebook):
    with pytest.raises(ValueError):
        add_pricebook_entry(pricebook, 10)


def test_update_pricebook_price_changes_and_persists(pricebook, product):
    entry = add_pricebook_entry(pricebook, 10, product=product)

    update_pricebook_price(entry, 12.50)

    entry.refresh_from_db()
    assert str(entry.price) == "12.50"


def test_deactivate_pricebook_entry_does_not_soft_delete(pricebook, product):
    entry = add_pricebook_entry(pricebook, 10, product=product)

    deactivate_pricebook_entry(entry)

    entry.refresh_from_db()
    assert entry.is_active is False
    assert entry.is_deleted is False
    # Still reachable via the unfiltered manager and via the constraint-safe
    # "not active" check — proving it's a business flag, not a soft delete.
    assert PriceBookEntry.objects.filter(pk=entry.pk).exists()
