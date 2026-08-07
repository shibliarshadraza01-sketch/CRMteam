"""CP10: django-filter ``FilterSet`` classes for the CRM API.

Plain field filters (``status``, ``owner``, ``organization``, ``industry``,
``is_active``, ``source``) are declared via ``Meta.fields`` — django-filter
infers an exact-match filter for each from the model field, no custom code
needed. The one exception is `Lead`'s ``converted`` filter: `Lead` has no
boolean `converted` column (see CP9's `models.py`), only a derived
``is_converted`` property, so it's backed by a small ``BooleanFilter``
whose ``method`` delegates to CP9's OWN ``LeadQuerySet.converted()``/
``unconverted()`` queryset methods — reused, not reimplemented.
"""
import django_filters

from .models import Address, ContactPerson, Customer, Lead
from .opportunities import Opportunity


class CustomerFilterSet(django_filters.FilterSet):
    class Meta:
        model = Customer
        fields = ["status", "owner", "organization", "industry", "is_active"]


class LeadFilterSet(django_filters.FilterSet):
    converted = django_filters.BooleanFilter(method="filter_converted", label="Converted")

    class Meta:
        model = Lead
        fields = ["status", "owner", "source"]

    def filter_converted(self, queryset, name, value):
        return queryset.converted() if value else queryset.unconverted()


class ContactPersonFilterSet(django_filters.FilterSet):
    class Meta:
        model = ContactPerson
        fields = ["customer", "is_primary"]


class AddressFilterSet(django_filters.FilterSet):
    class Meta:
        model = Address
        fields = ["customer", "address_type"]


class OpportunityFilterSet(django_filters.FilterSet):
    """``closed``/``won`` are explicit aliases for the model's own
    ``is_closed``/``is_won`` fields — shorter, CP11-spec-literal query
    param names (``?closed=true``) rather than requiring
    ``?is_closed=true``. Date/value RANGES use explicit ``_from``/``_to``
    and ``_min``/``_max`` filters (rather than django-filter's
    ``DateFromToRangeFilter``, which expects a single multi-value param)
    so each bound is independently optional in a plain query string —
    ``?value_min=10000`` alone is a valid "at least $10k" filter with no
    upper bound required.
    """

    closed = django_filters.BooleanFilter(field_name="is_closed")
    won = django_filters.BooleanFilter(field_name="is_won")

    expected_close_date_from = django_filters.DateFilter(field_name="expected_close_date", lookup_expr="gte")
    expected_close_date_to = django_filters.DateFilter(field_name="expected_close_date", lookup_expr="lte")
    actual_close_date_from = django_filters.DateFilter(field_name="actual_close_date", lookup_expr="gte")
    actual_close_date_to = django_filters.DateFilter(field_name="actual_close_date", lookup_expr="lte")

    value_min = django_filters.NumberFilter(field_name="value", lookup_expr="gte")
    value_max = django_filters.NumberFilter(field_name="value", lookup_expr="lte")

    class Meta:
        model = Opportunity
        fields = ["stage", "owner", "customer"]
