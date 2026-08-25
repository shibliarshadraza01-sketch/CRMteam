"""Phase 4 transaction-safety audit: recording a payment.

``test_payment_transactions.py`` already covers the business rules
(positive amount, no overpayment, no payment against a cancelled invoice,
status moving to PARTIAL/PAID). This module covers what those tests
deliberately do not: whether the DATABASE is consistent when something
fails between ``record_payment()``'s two writes, and whether the
"no overpayment, ever" rule survives being read back from a stale value.

Two distinct defects motivated these tests:

1. *Partial write.* The ``PaymentTransaction`` row and the parent invoice's
   recalculated ``status``/``paid_at`` are separate writes. Un-transacted,
   a failure between them recorded real money against an invoice whose
   ledger still said ``SENT`` with the old balance.

2. *Stale-annotation status bug.* ``InvoiceViewSet.get_queryset()``
   annotates ``_amount_paid_annotated``, and ``Invoice.amount_paid``
   prefers that annotation when present. It is computed once when the
   queryset is evaluated and does NOT change when ``record_payment()``
   inserts a payment — so reading it back to decide the invoice's new
   status compares against a PRE-payment total. An invoice paid in full
   through such an instance stayed at ``SENT``/``PARTIAL`` forever, and its
   remaining-balance check let further payments through on top. The fix
   re-fetches the invoice under ``select_for_update()``, which both locks
   the row against a concurrent overpayment and guarantees a live
   aggregate. ``test_record_payment_ignores_a_stale_annotated_amount_paid``
   is the regression test for exactly that.
"""
import pytest
from decimal import Decimal

from apps.sales.models import Invoice, PaymentTransaction
from apps.sales.services import add_invoice_item, record_payment

PAYMENTS_URL = "/api/v1/sales/payments/"


@pytest.fixture
def priced_invoice(db, invoice):
    """An invoice with a real 100.00 total, from a real line item."""
    add_invoice_item(invoice, "Consulting", 1, Decimal("100.00"))
    invoice.refresh_from_db()
    return invoice


class _Boom(Exception):
    """An unmistakably-ours downstream failure — see the sibling test module
    in ``apps/crm/tests/test_lead_conversion_atomicity.py``.
    """


# --------------------------------------------------------------------------
# (1) valid request -> the expected records really are created
# --------------------------------------------------------------------------


def test_valid_payment_creates_one_transaction_and_updates_the_invoice(priced_invoice):
    payments_before = PaymentTransaction.objects.count()

    payment = record_payment(priced_invoice, Decimal("40.00"))

    assert PaymentTransaction.objects.count() == payments_before + 1
    priced_invoice.refresh_from_db()
    assert priced_invoice.status == Invoice.Status.PARTIAL
    assert priced_invoice.amount_paid == Decimal("40.00")
    assert priced_invoice.balance == Decimal("60.00")
    assert payment.invoice_id == priced_invoice.pk


def test_paying_the_full_balance_marks_the_invoice_paid(priced_invoice):
    record_payment(priced_invoice, Decimal("100.00"))

    priced_invoice.refresh_from_db()
    assert priced_invoice.status == Invoice.Status.PAID
    assert priced_invoice.paid_at is not None
    assert priced_invoice.balance == Decimal("0.00")


# --------------------------------------------------------------------------
# (2) invalid request -> zero unintended records
# --------------------------------------------------------------------------


@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("-10.00")])
def test_a_non_positive_amount_records_nothing(priced_invoice, amount):
    payments_before = PaymentTransaction.objects.count()

    with pytest.raises(ValueError):
        record_payment(priced_invoice, amount)

    assert PaymentTransaction.objects.count() == payments_before
    priced_invoice.refresh_from_db()
    assert priced_invoice.status != Invoice.Status.PAID


def test_an_overpayment_records_nothing(priced_invoice):
    record_payment(priced_invoice, Decimal("90.00"))
    payments_after_valid = PaymentTransaction.objects.count()

    with pytest.raises(ValueError, match="exceeds the remaining balance"):
        record_payment(priced_invoice, Decimal("20.00"))

    assert PaymentTransaction.objects.count() == payments_after_valid
    priced_invoice.refresh_from_db()
    assert priced_invoice.amount_paid == Decimal("90.00")


def test_a_payment_against_a_cancelled_invoice_records_nothing(priced_invoice):
    from apps.sales.services import cancel_invoice

    cancel_invoice(priced_invoice)
    payments_before = PaymentTransaction.objects.count()

    with pytest.raises(ValueError, match="cancelled"):
        record_payment(priced_invoice, Decimal("10.00"))

    assert PaymentTransaction.objects.count() == payments_before


# --------------------------------------------------------------------------
# (3) downstream failure -> rollback
# --------------------------------------------------------------------------


def test_payment_is_rolled_back_when_the_invoice_status_update_fails(priced_invoice, monkeypatch):
    """The exact partial-write window: the PaymentTransaction row is in,
    the invoice's own status save then fails. Money recorded against a
    ledger that never learned about it is the outcome under test.
    """
    payments_before = PaymentTransaction.objects.count()
    original_save = Invoice.save

    def exploding_save(self, *args, **kwargs):
        raise _Boom("simulated failure recalculating the invoice status")

    monkeypatch.setattr(Invoice, "save", exploding_save)

    with pytest.raises(_Boom):
        record_payment(priced_invoice, Decimal("100.00"))

    monkeypatch.setattr(Invoice, "save", original_save)
    assert PaymentTransaction.objects.count() == payments_before
    priced_invoice.refresh_from_db()
    assert priced_invoice.amount_paid == Decimal("0.00")
    assert priced_invoice.status != Invoice.Status.PAID


def test_record_payment_ignores_a_stale_annotated_amount_paid(priced_invoice):
    """Regression test for the stale-annotation status bug described in this
    module's docstring.

    An invoice fetched through ``InvoiceViewSet``'s annotating queryset
    carries ``_amount_paid_annotated``, which ``Invoice.amount_paid``
    prefers. Paying such an instance in full must still move it to ``PAID``
    — the decision has to come from a live aggregate, not from a number
    captured before the payment existed.
    """
    from django.db.models import DecimalField, Q, Sum, Value
    from django.db.models.functions import Coalesce

    annotated = (
        Invoice.objects.filter(pk=priced_invoice.pk)
        .annotate(
            _amount_paid_annotated=Coalesce(
                Sum("payments__amount", filter=Q(payments__is_deleted=False)),
                Value(0),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        .get()
    )
    # Captured when the queryset was evaluated: nothing paid yet.
    assert annotated._amount_paid_annotated == Decimal("0.00")

    record_payment(annotated, Decimal("100.00"))

    priced_invoice.refresh_from_db()
    assert priced_invoice.amount_paid == Decimal("100.00")
    assert priced_invoice.status == Invoice.Status.PAID
    assert priced_invoice.paid_at is not None


def test_a_second_payment_through_a_stale_instance_cannot_overpay(priced_invoice):
    """The balance check must also read live, not from the stale annotation
    — otherwise the same instance could be used to pay the full amount
    twice.
    """
    from django.db.models import DecimalField, Q, Sum, Value
    from django.db.models.functions import Coalesce

    def _annotated():
        return (
            Invoice.objects.filter(pk=priced_invoice.pk)
            .annotate(
                _amount_paid_annotated=Coalesce(
                    Sum("payments__amount", filter=Q(payments__is_deleted=False)),
                    Value(0),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
            .get()
        )

    stale = _annotated()
    record_payment(stale, Decimal("100.00"))

    # `stale` still believes nothing has been paid.
    assert stale._amount_paid_annotated == Decimal("0.00")
    with pytest.raises(ValueError, match="exceeds the remaining balance"):
        record_payment(stale, Decimal("100.00"))

    priced_invoice.refresh_from_db()
    assert priced_invoice.amount_paid == Decimal("100.00")


# --------------------------------------------------------------------------
# (4) permission failure -> zero mutation, over real HTTP
# --------------------------------------------------------------------------


def test_employee_cannot_record_a_payment_on_an_unreachable_invoice(
    api_client, other_employee, priced_invoice
):
    """The invoice belongs to somebody outside this employee's scope.
    ``assert_object_accessible()`` must refuse it, and — the point of this
    test — no PaymentTransaction may exist afterwards.
    """
    api_client.force_authenticate(other_employee)
    payments_before = PaymentTransaction.objects.count()

    response = api_client.post(
        PAYMENTS_URL,
        {"invoice": priced_invoice.pk, "amount": "10.00"},
        format="json",
    )

    assert response.status_code in (403, 404)
    assert PaymentTransaction.objects.count() == payments_before
    priced_invoice.refresh_from_db()
    assert priced_invoice.amount_paid == Decimal("0.00")
    assert priced_invoice.status != Invoice.Status.PARTIAL


def test_overpayment_over_http_returns_400_and_records_nothing(api_client, owner, priced_invoice, super_admin):
    """The API-level counterpart of the service test above: a refused
    payment must be refused in the database too, with a message that names
    the real remaining balance rather than a generic failure.
    """
    # Revenue/Payments audit pass: recording a payment is Super-Admin-only now.
    api_client.force_authenticate(super_admin)
    payments_before = PaymentTransaction.objects.count()

    response = api_client.post(
        PAYMENTS_URL,
        {"invoice": priced_invoice.pk, "amount": "500.00"},
        format="json",
    )

    assert response.status_code == 400
    assert "exceeds the remaining balance" in str(response.data)
    assert PaymentTransaction.objects.count() == payments_before


def test_valid_payment_over_http_creates_the_row_and_updates_status(api_client, owner, priced_invoice, super_admin):
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        PAYMENTS_URL,
        {"invoice": priced_invoice.pk, "amount": "100.00"},
        format="json",
    )

    assert response.status_code == 201
    assert PaymentTransaction.objects.filter(pk=response.data["id"]).exists()
    priced_invoice.refresh_from_db()
    assert priced_invoice.status == Invoice.Status.PAID
