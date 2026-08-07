"""CP12: tests for apps/sales/filters.py."""
import pytest

from apps.sales.filters import InvoiceFilterSet, QuoteFilterSet
from apps.sales.models import Invoice, Quote

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_quote_filterset_declares_spec_fields():
    assert set(QuoteFilterSet.Meta.fields) == {"owner", "customer", "status"}


def test_quote_filterset_declares_valid_until_range():
    assert "valid_until_from" in QuoteFilterSet.declared_filters
    assert "valid_until_to" in QuoteFilterSet.declared_filters


def test_invoice_filterset_declares_spec_fields():
    assert set(InvoiceFilterSet.Meta.fields) == {"owner", "customer", "status"}


def test_invoice_filterset_declares_due_date_range_and_paid():
    assert "due_date_from" in InvoiceFilterSet.declared_filters
    assert "due_date_to" in InvoiceFilterSet.declared_filters
    assert "paid" in InvoiceFilterSet.declared_filters


def test_paid_filter_builds_query_without_hitting_db():
    filterset = InvoiceFilterSet(data={"paid": "true"}, queryset=Invoice.objects.all())
    assert filterset.is_valid()
    assert len(filterset.qs.query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_valid_until_range_filter_matches_real_rows(customer):
    import datetime

    early = Quote.objects.create(customer=customer, quote_number="Q-E", valid_until=datetime.date(2026, 1, 1))
    Quote.objects.create(customer=customer, quote_number="Q-L", valid_until=datetime.date(2026, 6, 1))

    filterset = QuoteFilterSet(data={"valid_until_to": "2026-03-01"}, queryset=Quote.objects.all())
    assert list(filterset.qs) == [early]


@pytest.mark.django_db
def test_paid_filter_matches_real_rows(customer):
    paid = Invoice.objects.create(customer=customer, invoice_number="INV-P", status=Invoice.Status.PAID)
    Invoice.objects.create(customer=customer, invoice_number="INV-S", status=Invoice.Status.SENT)

    filterset = InvoiceFilterSet(data={"paid": "true"}, queryset=Invoice.objects.all())
    assert list(filterset.qs) == [paid]
