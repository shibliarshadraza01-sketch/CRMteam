"""CP12: tests for apps/sales/services.py — quoting/invoicing business
rules. Every test requires a real database.
"""
import pytest
from decimal import Decimal

from apps.sales.models import Invoice, InvoiceItem, Quote, QuoteItem
from apps.sales.services import (
    add_invoice_item,
    add_quote_item,
    approve_quote,
    cancel_invoice,
    convert_quote_to_invoice,
    create_invoice,
    create_quote,
    mark_invoice_paid,
    reject_quote,
    submit_quote,
)

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------
# create_quote() / add_quote_item() / recalculate_quote_totals()
# --------------------------------------------------------------------------


def test_create_quote_basic(customer):
    quote = create_quote(customer, "Q-1")
    assert quote.status == Quote.Status.DRAFT
    assert quote.subtotal == 0


def test_add_quote_item_computes_total_price(customer):
    quote = create_quote(customer, "Q-2")
    item = add_quote_item(quote, "Widget", 3, Decimal("10.00"))
    assert item.total_price == Decimal("30.00")


def test_add_quote_item_recalculates_quote_totals(customer):
    quote = create_quote(customer, "Q-3", tax=Decimal("5.00"))
    add_quote_item(quote, "Widget", 2, Decimal("10.00"))
    add_quote_item(quote, "Gadget", 1, Decimal("15.00"))

    quote.refresh_from_db()
    assert quote.subtotal == Decimal("35.00")
    assert quote.total == Decimal("40.00")  # subtotal + tax


def test_add_quote_item_auto_assigns_ordering(customer):
    quote = create_quote(customer, "Q-4")
    first = add_quote_item(quote, "A", 1, Decimal("1.00"))
    second = add_quote_item(quote, "B", 1, Decimal("1.00"))

    assert first.ordering == 0
    assert second.ordering == 1


def test_add_quote_item_respects_explicit_ordering(customer):
    quote = create_quote(customer, "Q-5")
    item = add_quote_item(quote, "A", 1, Decimal("1.00"), ordering=99)
    assert item.ordering == 99


# --------------------------------------------------------------------------
# submit_quote() / approve_quote() / reject_quote()
# --------------------------------------------------------------------------


def test_submit_quote_moves_draft_to_submitted(quote):
    submit_quote(quote)
    assert quote.status == Quote.Status.SUBMITTED


def test_submit_quote_rejects_non_draft(quote):
    submit_quote(quote)
    with pytest.raises(ValueError):
        submit_quote(quote)


def test_approve_quote_rejects_draft(quote):
    with pytest.raises(ValueError):
        approve_quote(quote, None)


def test_approve_quote_sets_approved_by_and_at(quote, super_admin):
    submit_quote(quote)
    approve_quote(quote, super_admin)

    assert quote.status == Quote.Status.APPROVED
    assert quote.approved_by_id == super_admin.id
    assert quote.approved_at is not None


def test_reject_quote_rejects_draft(quote):
    with pytest.raises(ValueError):
        reject_quote(quote)


def test_reject_quote_rejects_already_approved(quote, super_admin):
    submit_quote(quote)
    approve_quote(quote, super_admin)
    with pytest.raises(ValueError):
        reject_quote(quote)


def test_reject_quote_from_submitted(quote):
    submit_quote(quote)
    reject_quote(quote)
    assert quote.status == Quote.Status.REJECTED


# --------------------------------------------------------------------------
# convert_quote_to_invoice()
# --------------------------------------------------------------------------


def test_convert_quote_rejects_non_approved(quote):
    with pytest.raises(ValueError):
        convert_quote_to_invoice(quote, "INV-1")


def test_convert_approved_quote_creates_invoice(approved_quote):
    invoice = convert_quote_to_invoice(approved_quote, "INV-2")

    assert isinstance(invoice, Invoice)
    assert invoice.status == Invoice.Status.SENT
    assert invoice.customer_id == approved_quote.customer_id


def test_convert_quote_marks_quote_converted(approved_quote):
    convert_quote_to_invoice(approved_quote, "INV-3")
    approved_quote.refresh_from_db()
    assert approved_quote.status == Quote.Status.CONVERTED


def test_convert_quote_copies_line_items(approved_quote):
    add_quote_item(approved_quote, "Widget", 2, Decimal("10.00"))

    invoice = convert_quote_to_invoice(approved_quote, "INV-4")

    assert invoice.items.count() == 1
    assert invoice.subtotal == Decimal("20.00")


def test_convert_quote_is_idempotent(approved_quote):
    first = convert_quote_to_invoice(approved_quote, "INV-5")
    second = convert_quote_to_invoice(approved_quote, "INV-5-DUPLICATE-ATTEMPT")

    assert first.id == second.id
    assert Invoice.objects.filter(quote=approved_quote).count() == 1


def test_convert_quote_carries_over_tax(customer):
    quote = create_quote(customer, "Q-TAX", tax=Decimal("7.50"))
    from apps.sales.services import approve_quote, submit_quote

    submit_quote(quote)
    approve_quote(quote, None)

    invoice = convert_quote_to_invoice(quote, "INV-TAX")

    assert invoice.tax == Decimal("7.50")


# --------------------------------------------------------------------------
# create_invoice() / add_invoice_item() / recalculate_invoice_totals()
# --------------------------------------------------------------------------


def test_create_invoice_defaults_to_draft(customer):
    invoice = create_invoice(customer, "INV-D1")
    assert invoice.status == Invoice.Status.DRAFT


def test_add_invoice_item_computes_total_and_recalculates(customer):
    invoice = create_invoice(customer, "INV-D2")
    add_invoice_item(invoice, "Widget", 4, Decimal("2.50"))

    invoice.refresh_from_db()
    assert invoice.subtotal == Decimal("10.00")
    assert invoice.total == Decimal("10.00")


# --------------------------------------------------------------------------
# mark_invoice_paid() / cancel_invoice()
# --------------------------------------------------------------------------


def test_mark_invoice_paid_sets_status_and_paid_at(invoice):
    mark_invoice_paid(invoice)
    assert invoice.status == Invoice.Status.PAID
    assert invoice.paid_at is not None


def test_mark_invoice_paid_rejects_already_paid(invoice):
    mark_invoice_paid(invoice)
    with pytest.raises(ValueError):
        mark_invoice_paid(invoice)


def test_mark_invoice_paid_rejects_cancelled(invoice):
    cancel_invoice(invoice)
    with pytest.raises(ValueError):
        mark_invoice_paid(invoice)


def test_cancel_invoice_sets_status(invoice):
    cancel_invoice(invoice)
    assert invoice.status == Invoice.Status.CANCELLED


def test_cancel_invoice_rejects_already_cancelled(invoice):
    cancel_invoice(invoice)
    with pytest.raises(ValueError):
        cancel_invoice(invoice)


def test_cancel_invoice_rejects_paid(invoice):
    mark_invoice_paid(invoice)
    with pytest.raises(ValueError):
        cancel_invoice(invoice)
