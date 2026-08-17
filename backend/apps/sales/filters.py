"""CP12: django-filter ``FilterSet`` classes for the sales API."""
import django_filters

from .models import Invoice, PaymentTransaction, Quote


class QuoteFilterSet(django_filters.FilterSet):
    valid_until_from = django_filters.DateFilter(field_name="valid_until", lookup_expr="gte")
    valid_until_to = django_filters.DateFilter(field_name="valid_until", lookup_expr="lte")

    class Meta:
        model = Quote
        fields = ["owner", "customer", "status"]


class InvoiceFilterSet(django_filters.FilterSet):
    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    # "paid" is a friendlier boolean alias for `status=PAID` — CP12's
    # spec literally lists "paid" as its own filter, distinct from the
    # general `status` filter already covering PAID/DRAFT/SENT/CANCELLED.
    paid = django_filters.BooleanFilter(method="filter_paid", label="Paid")

    class Meta:
        model = Invoice
        fields = ["owner", "customer", "status"]

    def filter_paid(self, queryset, name, value):
        return queryset.paid() if value else queryset.exclude(status=Invoice.Status.PAID)


class PaymentTransactionFilterSet(django_filters.FilterSet):
    paid_at_from = django_filters.DateFilter(field_name="paid_at", lookup_expr="gte")
    paid_at_to = django_filters.DateFilter(field_name="paid_at", lookup_expr="lte")

    class Meta:
        model = PaymentTransaction
        fields = ["invoice", "method"]
