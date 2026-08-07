"""CP13: reusable service functions for the catalog domain.

Following the CP5/CP8/CP9/CP11/CP12 pattern: narrow, single-purpose
functions for operations with real behavior beyond a single ORM call.
"""
from .models import PriceBook, PriceBookEntry, Product, Service


def create_product(name, sku, *, default_price=0, currency="USD", description="", **extra_fields):
    """Create a ``Product``. A thin wrapper — kept as a service function
    for the same single-seam reasoning as CP9's ``create_lead()``: a
    future intake rule (SKU format validation, duplicate-name detection)
    has one place to be added.
    """
    return Product.objects.create(
        name=name, sku=sku, default_price=default_price, currency=currency, description=description, **extra_fields
    )


def create_service(name, code, *, default_rate=0, currency="USD", description="", **extra_fields):
    """Create a ``Service``. Same shape and reasoning as ``create_product()``."""
    return Service.objects.create(
        name=name, code=code, default_rate=default_rate, currency=currency, description=description, **extra_fields
    )


def create_pricebook(name, *, currency="USD", description="", **extra_fields):
    """Create a ``PriceBook``. Same shape and reasoning as ``create_product()``."""
    return PriceBook.objects.create(name=name, currency=currency, description=description, **extra_fields)


def add_pricebook_entry(price_book, price, *, product=None, service=None):
    """Add a priced ``PriceBookEntry`` to ``price_book``.

    Exactly one of ``product``/``service`` must be given — raises
    ``ValueError`` otherwise, mirroring the model's own
    ``exactly_one_of_product_or_service`` check constraint (the DB
    constraint remains the real, unbreakable guarantee; this is purely a
    friendlier error than a raw ``IntegrityError``, the same "constraint
    is the source of truth, validation is UX" layering CP9 established for
    `ContactPerson`'s primary-contact rule).
    """
    if (product is None) == (service is None):
        raise ValueError("Provide exactly one of `product` or `service`, not both and not neither.")

    return PriceBookEntry.objects.create(price_book=price_book, product=product, service=service, price=price)


def update_pricebook_price(entry, new_price):
    """Change an existing ``PriceBookEntry``'s ``price``. Kept as a
    service function (rather than a bare ``entry.price = x; entry.save()``
    at call sites) so a future rule (e.g. "log a price-change history
    entry") has exactly one place to be added.
    """
    entry.price = new_price
    entry.save(update_fields=["price", "updated_at"])
    return entry


def deactivate_pricebook_entry(entry):
    """Set a ``PriceBookEntry``'s ``is_active`` to ``False`` — retiring an
    entry from active use WITHOUT soft-deleting it (the same "business
    flag is a separate axis from soft delete" distinction CP9's `Customer`
    established — a deactivated entry is still visible for historical
    reporting, e.g. "what did we used to charge for this").
    """
    entry.is_active = False
    entry.save(update_fields=["is_active", "updated_at"])
    return entry


__all__ = [
    "create_product",
    "create_service",
    "create_pricebook",
    "add_pricebook_entry",
    "update_pricebook_price",
    "deactivate_pricebook_entry",
]
