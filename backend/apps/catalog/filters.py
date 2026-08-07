"""CP13: django-filter ``FilterSet`` classes for the catalog API."""
import django_filters

from .models import PriceBook, PriceBookEntry, Product, Service


class ProductFilterSet(django_filters.FilterSet):
    class Meta:
        model = Product
        fields = ["is_active", "currency"]


class ServiceFilterSet(django_filters.FilterSet):
    class Meta:
        model = Service
        fields = ["is_active", "currency"]


class PriceBookFilterSet(django_filters.FilterSet):
    class Meta:
        model = PriceBook
        fields = ["is_active", "currency"]


class PriceBookEntryFilterSet(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = PriceBookEntry
        fields = ["price_book", "product", "service", "is_active"]
