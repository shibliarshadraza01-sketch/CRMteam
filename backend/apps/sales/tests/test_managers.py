"""CP12: tests for QuoteQuerySet/InvoiceQuerySet."""
import datetime

import pytest

from apps.sales.models import Invoice, Quote

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_quote_manager_has_expected_helpers():
    for helper in ("draft", "submitted", "approved", "rejected", "converted"):
        assert hasattr(Quote.objects, helper)


def test_quote_helpers_build_filters_without_hitting_db():
    for helper in ("draft", "submitted", "approved", "rejected", "converted"):
        queryset = getattr(Quote.objects, helper)()
        assert len(queryset.query.where) > 0


def test_invoice_manager_has_expected_helpers():
    for helper in ("draft", "sent", "paid", "cancelled", "overdue"):
        assert hasattr(Invoice.objects, helper)


def test_invoice_status_helpers_build_filters_without_hitting_db():
    for helper in ("draft", "sent", "paid", "cancelled"):
        queryset = getattr(Invoice.objects, helper)()
        assert len(queryset.query.where) > 0


def test_overdue_accepts_injectable_today_without_hitting_db():
    queryset = Invoice.objects.overdue(today=datetime.date(2026, 3, 15))
    assert "due_date" in str(queryset.query.where)


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_quote_status_helpers_match_real_rows(customer):
    draft = Quote.objects.create(customer=customer, quote_number="Q-D", status=Quote.Status.DRAFT)
    submitted = Quote.objects.create(customer=customer, quote_number="Q-S", status=Quote.Status.SUBMITTED)

    assert list(Quote.objects.draft()) == [draft]
    assert list(Quote.objects.submitted()) == [submitted]


@pytest.mark.django_db
def test_invoice_overdue_excludes_paid_and_cancelled(customer):
    today = datetime.date(2026, 3, 15)
    overdue_sent = Invoice.objects.create(
        customer=customer, invoice_number="INV-OD", status=Invoice.Status.SENT, due_date=datetime.date(2026, 1, 1)
    )
    Invoice.objects.create(
        customer=customer, invoice_number="INV-PAID", status=Invoice.Status.PAID, due_date=datetime.date(2026, 1, 1)
    )
    Invoice.objects.create(
        customer=customer, invoice_number="INV-CANC", status=Invoice.Status.CANCELLED, due_date=datetime.date(2026, 1, 1)
    )
    Invoice.objects.create(
        customer=customer, invoice_number="INV-FUTURE", status=Invoice.Status.SENT, due_date=datetime.date(2026, 6, 1)
    )

    result = Invoice.objects.overdue(today=today)

    assert list(result) == [overdue_sent]
