"""CP13: the catalog domain's REST API.

Built from CP7's ``SoftDeleteAuditModelViewSetMixin`` (soft-delete-on-
DELETE, audit stamping, ``restore``/``hard-delete`` actions), exactly like
every CP9+ viewset. Deliberately does NOT reuse CP10's
``_CrmModelViewSet`` (``apps.crm.views``) — that base's `get_queryset()`
scopes every queryset through ``scope_queryset_for_user()``/`owner_field`,
which assumes an `owner` FK that catalog models don't have (see
``permissions.py``). Reusing it here would mean either faking an owner
concept catalog data doesn't have, or silently no-op-ing the scoping —
both worse than a small, honest, catalog-specific base with no ownership
layer at all.

CP20: the no-ownership base shape itself (no PUT, active-vs-unfiltered
``get_queryset()``) is shared with CP15's/CP19's own reference-data
viewsets and lives in ``apps.core.views.ReferenceDataModelViewSetMixin``
— only ``permission_classes`` differs per app, and stays declared here.
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.views import ReferenceDataModelViewSetMixin

from .filters import (
    PriceBookEntryFilterSet,
    PriceBookFilterSet,
    ProductFilterSet,
    ServiceFilterSet,
)
from .models import PriceBook, PriceBookEntry, Product, Service
from .permissions import CatalogWritePermission
from .serializers import (
    PriceBookDetailSerializer,
    PriceBookEntryDetailSerializer,
    PriceBookEntrySerializer,
    PriceBookSerializer,
    ProductSerializer,
    ServiceSerializer,
)


class _CatalogModelViewSet(ReferenceDataModelViewSetMixin, viewsets.ModelViewSet):
    """Shared base for every CP13 viewset — read: any authenticated user;
    write: Manager or above (see ``permissions.py`` for how
    ``CatalogWritePermission`` is composed with zero new logic).
    """

    permission_classes = [IsAuthenticated, CatalogWritePermission]


class ProductViewSet(_CatalogModelViewSet):
    base_manager = Product.objects
    base_active_manager = Product.active_objects
    serializer_class = ProductSerializer
    filterset_class = ProductFilterSet
    search_fields = ["name", "sku", "description"]
    ordering_fields = ["name", "default_price", "created_at", "updated_at"]
    ordering = ["name"]


class ServiceViewSet(_CatalogModelViewSet):
    base_manager = Service.objects
    base_active_manager = Service.active_objects
    serializer_class = ServiceSerializer
    filterset_class = ServiceFilterSet
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "default_rate", "created_at", "updated_at"]
    ordering = ["name"]


class PriceBookViewSet(_CatalogModelViewSet):
    base_manager = PriceBook.objects
    base_active_manager = PriceBook.active_objects
    serializer_class = PriceBookSerializer
    filterset_class = PriceBookFilterSet
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("entries")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PriceBookDetailSerializer
        return PriceBookSerializer


class PriceBookEntryViewSet(_CatalogModelViewSet):
    base_manager = PriceBookEntry.objects
    base_active_manager = PriceBookEntry.active_objects
    serializer_class = PriceBookEntrySerializer
    filterset_class = PriceBookEntryFilterSet
    search_fields = ["product__name", "product__sku", "service__name", "service__code"]
    ordering_fields = ["price", "created_at", "updated_at"]
    ordering = ["price_book", "product", "service"]

    def get_queryset(self):
        return super().get_queryset().select_related("price_book", "product", "service")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PriceBookEntryDetailSerializer
        return PriceBookEntrySerializer
