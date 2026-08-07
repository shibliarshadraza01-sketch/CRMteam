"""CP13: the sellable catalog — products, services, and their prices.

    Product  --\\
                >-- PriceBookEntry --< PriceBook
    Service  --/

Every model inherits ``apps.core.models.SoftDeleteTimeStampedModel``
(CP7), exactly like every CP9+ CRM/sales record — a discontinued product
or a retired price book should be reversibly removable, not permanently
erased (the same "delete means archive" reasoning CP9 established).

Unlike `Customer`/`Lead`/`Opportunity`/`Quote`/`Invoice`, none of these
models has an `owner` FK — catalog data (what exists to be sold, at what
list price) is shared reference data, not a per-salesperson record. See
``permissions.py`` for what this means for access control.
"""
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteQuerySet, SoftDeleteTimeStampedModel


# --------------------------------------------------------------------------
# Product
# --------------------------------------------------------------------------


class CatalogItemQuerySet(SoftDeleteQuerySet):
    """Shared by ``Product``/``Service``/``PriceBook`` — all three have the
    same "two independent booleans" shape CP9's `Customer` established:
    soft-deleted (``is_deleted``, inherited from CP7) and business-active
    (``is_active``, this app's own flag — a discontinued product/service/
    price book you're still keeping visible for historical reporting is
    `is_deleted=False, is_active=False`).
    """

    def active(self):
        return super().active().filter(is_active=True)


class CatalogItemManager(models.Manager.from_queryset(CatalogItemQuerySet)):
    """The unfiltered ``objects`` manager, per CP7's soft-delete
    convention (see ``apps.core.models.SoftDeleteManager``'s docstring).
    """


class ActiveCatalogItemManager(CatalogItemManager):
    """The ``active_objects`` manager — not-deleted AND business-active."""

    def get_queryset(self):
        return super().get_queryset().active()


class Product(SoftDeleteTimeStampedModel):
    name = models.CharField(_("name"), max_length=200)
    sku = models.CharField(_("SKU"), max_length=64, unique=True, help_text=_("Stock keeping unit — a unique catalog identifier."))
    description = models.TextField(_("description"), blank=True, default="")
    default_price = models.DecimalField(_("default price"), max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(_("currency"), max_length=3, default="USD")
    is_active = models.BooleanField(
        _("is active"), default=True, db_index=True,
        help_text=_("Business-status flag (e.g. discontinued), independent of soft delete."),
    )

    objects = CatalogItemManager()
    active_objects = ActiveCatalogItemManager()

    class Meta:
        ordering = ["name"]
        verbose_name = _("product")
        verbose_name_plural = _("products")
        indexes = [
            models.Index(fields=["is_active"], name="catalog_product_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------


class Service(SoftDeleteTimeStampedModel):
    name = models.CharField(_("name"), max_length=200)
    code = models.CharField(_("code"), max_length=64, unique=True, help_text=_("A unique catalog identifier (services aren't stocked, so `code`, not `sku`)."))
    description = models.TextField(_("description"), blank=True, default="")
    default_rate = models.DecimalField(
        _("default rate"), max_digits=12, decimal_places=2, default=0,
        help_text=_("Default billing rate — e.g. per hour or per engagement, unit is not enforced by this model."),
    )
    currency = models.CharField(_("currency"), max_length=3, default="USD")
    is_active = models.BooleanField(_("is active"), default=True, db_index=True)

    objects = CatalogItemManager()
    active_objects = ActiveCatalogItemManager()

    class Meta:
        ordering = ["name"]
        verbose_name = _("service")
        verbose_name_plural = _("services")
        indexes = [
            models.Index(fields=["is_active"], name="catalog_service_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


# --------------------------------------------------------------------------
# PriceBook
# --------------------------------------------------------------------------


class PriceBook(SoftDeleteTimeStampedModel):
    name = models.CharField(_("name"), max_length=200, unique=True)
    description = models.TextField(_("description"), blank=True, default="")
    currency = models.CharField(
        _("currency"), max_length=3, default="USD",
        help_text=_("ISO 4217 currency code every entry in this price book is denominated in."),
    )
    is_active = models.BooleanField(_("is active"), default=True, db_index=True)

    objects = CatalogItemManager()
    active_objects = ActiveCatalogItemManager()

    class Meta:
        ordering = ["name"]
        verbose_name = _("price book")
        verbose_name_plural = _("price books")

    def __str__(self):
        return self.name


# --------------------------------------------------------------------------
# PriceBookEntry
# --------------------------------------------------------------------------


class PriceBookEntryQuerySet(SoftDeleteQuerySet):
    def active(self):
        return super().active().filter(is_active=True)

    def for_product(self, product):
        return self.filter(product=product)

    def for_service(self, service):
        return self.filter(service=service)


class PriceBookEntryManager(models.Manager.from_queryset(PriceBookEntryQuerySet)):
    """``PriceBookEntry.objects`` — unfiltered, per CP7's convention."""


class ActivePriceBookEntryManager(PriceBookEntryManager):
    """``PriceBookEntry.active_objects`` — not-deleted AND business-active."""

    def get_queryset(self):
        return super().get_queryset().active()


class PriceBookEntry(SoftDeleteTimeStampedModel):
    """One price, for exactly one ``Product`` OR ``Service`` (never both,
    never neither — enforced by the ``exactly_one_of_product_or_service``
    constraint below), in one ``PriceBook``.
    """

    price_book = models.ForeignKey(
        PriceBook, verbose_name=_("price book"), on_delete=models.CASCADE, related_name="entries"
    )
    product = models.ForeignKey(
        Product,
        verbose_name=_("product"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="pricebook_entries",
    )
    service = models.ForeignKey(
        Service,
        verbose_name=_("service"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="pricebook_entries",
    )
    price = models.DecimalField(_("price"), max_digits=12, decimal_places=2)
    is_active = models.BooleanField(
        _("is active"), default=True, db_index=True,
        help_text=_("Set False by apps.catalog.services.deactivate_pricebook_entry() to retire an entry without deleting it."),
    )

    objects = PriceBookEntryManager()
    active_objects = ActivePriceBookEntryManager()

    class Meta:
        ordering = ["price_book", "product", "service"]
        verbose_name = _("price book entry")
        verbose_name_plural = _("price book entries")
        constraints = [
            # Exactly one of product/service must be set — a DB-level
            # guarantee this checkpoint's services.add_pricebook_entry()
            # also validates up front for a friendlier error message (the
            # same "constraint is the real guarantee, validation is UX"
            # layering CP9 established for ContactPerson's primary-contact
            # rule).
            models.CheckConstraint(
                condition=(
                    (Q(product__isnull=False) & Q(service__isnull=True))
                    | (Q(product__isnull=True) & Q(service__isnull=False))
                ),
                name="catalog_entry_exactly_one_of_product_or_service",
            ),
            # At most one (active-or-not) entry per product per price book,
            # and separately per service per price book — partial unique
            # constraints, same technique as CP9's "at most one primary
            # contact per customer".
            models.UniqueConstraint(
                fields=["price_book", "product"],
                condition=Q(product__isnull=False),
                name="catalog_entry_unique_pricebook_product",
            ),
            models.UniqueConstraint(
                fields=["price_book", "service"],
                condition=Q(service__isnull=False),
                name="catalog_entry_unique_pricebook_service",
            ),
        ]
        indexes = [
            models.Index(fields=["price_book", "is_active"], name="catalog_entry_book_active_idx"),
        ]

    def __str__(self):
        item = self.product or self.service
        return f"{self.price_book.name} / {item} @ {self.price}"

    @property
    def item(self):
        """The ``Product`` or ``Service`` this entry prices — whichever of
        the two is actually set.
        """
        return self.product or self.service
