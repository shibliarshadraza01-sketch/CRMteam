"""CP13: serializers for the catalog domain.

Every serializer mixes in CP7's ``SoftDeleteTimeStampedSerializerMixin``,
exactly like every CP9+ serializer. ``PriceBookEntry`` follows the
writable/detail split established since CP9: ``PriceBookEntrySerializer``
(writable, `product`/`service` as plain PKs) for create/update,
``PriceBookEntryDetailSerializer`` (read-only, nests the priced
`Product`/`Service`) for `retrieve`. ``PriceBookDetailSerializer``
similarly nests a price book's entries. `Product`/`Service` have no
worth-nesting relation of their own and use one serializer
unconditionally, the same shape CP9's `ContactPerson`/`Address` used.
"""
from rest_framework import serializers

from apps.core.serializers import SoftDeleteTimeStampedSerializerMixin

from .models import PriceBook, PriceBookEntry, Product, Service


class _CatalogSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base: every catalog serializer gets the CP7 timestamp/audit/
    soft-delete field shape without repeating it per class.
    """


class ProductSerializer(_CatalogSerializer):
    class Meta:
        model = Product
        fields = [
            "id", "name", "sku", "description", "default_price", "currency", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class ServiceSerializer(_CatalogSerializer):
    class Meta:
        model = Service
        fields = [
            "id", "name", "code", "description", "default_rate", "currency", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class PriceBookSerializer(_CatalogSerializer):
    class Meta:
        model = PriceBook
        fields = [
            "id", "name", "description", "currency", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class PriceBookEntrySerializer(_CatalogSerializer):
    class Meta:
        model = PriceBookEntry
        fields = [
            "id", "price_book", "product", "service", "price", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]

    def validate(self, attrs):
        """Mirrors the model's ``exactly_one_of_product_or_service`` check
        constraint with a friendlier 400 — the constraint itself remains
        the actual source of truth (see ``models.py``), same pattern as
        CP9's `ContactPersonSerializer`.
        """
        product = attrs.get("product", getattr(self.instance, "product", None))
        service = attrs.get("service", getattr(self.instance, "service", None))
        if (product is None) == (service is None):
            raise serializers.ValidationError(
                "Provide exactly one of `product` or `service`, not both and not neither."
            )
        return attrs


class PriceBookEntryDetailSerializer(PriceBookEntrySerializer):
    """Read-only: nests the priced ``Product``/``Service`` and the price
    book's name.
    """

    product = ProductSerializer(read_only=True)
    service = ServiceSerializer(read_only=True)
    price_book_name = serializers.CharField(source="price_book.name", read_only=True)

    class Meta(PriceBookEntrySerializer.Meta):
        fields = PriceBookEntrySerializer.Meta.fields + ["price_book_name"]
        read_only_fields = fields


class PriceBookDetailSerializer(PriceBookSerializer):
    """Read-only: nests this price book's entries."""

    entries = PriceBookEntryDetailSerializer(many=True, read_only=True)

    class Meta(PriceBookSerializer.Meta):
        fields = PriceBookSerializer.Meta.fields + ["entries"]
        read_only_fields = fields
