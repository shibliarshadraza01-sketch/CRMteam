"""Final-completion-pass: partial payments, transaction history, and
balance tracking for ``Invoice`` — the original specification requires
tracking partial payments and payment history (see the frontend's own
Payments module copy: "track partial payments... view their payment
history"), which a plain paid/unpaid ``status`` boolean cannot express.
``PaymentTransaction`` and ``services.record_payment()`` add that without
touching ``mark_invoice_paid()``/``cancel_invoice()``'s existing,
already-tested all-at-once behavior.
"""
import pytest

from apps.sales.models import Invoice
from apps.sales.services import cancel_invoice, record_payment

pytestmark = pytest.mark.django_db

PAYMENTS_URL = "/api/v1/sales/payments/"


def _detail(url, pk):
    return f"{url}{pk}/"


@pytest.fixture
def priced_invoice(db, customer, owner):
    return Invoice.objects.create(customer=customer, invoice_number="INV-PAY-0001", owner=owner, total=100)


# --------------------------------------------------------------------------
# services.record_payment()
# --------------------------------------------------------------------------


def test_record_payment_creates_transaction(priced_invoice):
    transaction = record_payment(priced_invoice, 40)
    assert transaction.pk is not None
    assert transaction.amount == 40
    assert transaction.invoice_id == priced_invoice.pk


def test_record_payment_moves_invoice_to_partial(priced_invoice):
    record_payment(priced_invoice, 40)
    priced_invoice.refresh_from_db()
    assert priced_invoice.status == Invoice.Status.PARTIAL
    assert priced_invoice.paid_at is None


def test_record_payment_computes_amount_paid_and_balance(priced_invoice):
    record_payment(priced_invoice, 30)
    record_payment(priced_invoice, 20)
    priced_invoice.refresh_from_db()
    assert priced_invoice.amount_paid == 50
    assert priced_invoice.balance == 50


def test_record_payment_moves_invoice_to_paid_when_total_reached(priced_invoice):
    record_payment(priced_invoice, 60)
    record_payment(priced_invoice, 40)
    priced_invoice.refresh_from_db()
    assert priced_invoice.status == Invoice.Status.PAID
    assert priced_invoice.paid_at is not None
    assert priced_invoice.balance == 0


def test_record_payment_rejects_overpayment(priced_invoice):
    record_payment(priced_invoice, 90)
    with pytest.raises(ValueError):
        record_payment(priced_invoice, 20)


def test_record_payment_rejects_zero_amount(priced_invoice):
    with pytest.raises(ValueError):
        record_payment(priced_invoice, 0)


def test_record_payment_rejects_negative_amount(priced_invoice):
    with pytest.raises(ValueError):
        record_payment(priced_invoice, -10)


def test_record_payment_rejects_cancelled_invoice(priced_invoice):
    cancel_invoice(priced_invoice)
    with pytest.raises(ValueError):
        record_payment(priced_invoice, 10)


def test_invoice_amount_paid_ignores_soft_deleted_transactions(priced_invoice):
    transaction = record_payment(priced_invoice, 40)
    transaction.delete()
    priced_invoice.refresh_from_db()
    assert priced_invoice.amount_paid == 0
    assert priced_invoice.balance == 100


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------


def test_create_payment_via_api(api_client, priced_invoice, owner):
    api_client.force_authenticate(owner)
    response = api_client.post(PAYMENTS_URL, {"invoice": priced_invoice.pk, "amount": "25.00"})
    assert response.status_code == 201
    assert response.data["recorded_by"] == owner.pk
    priced_invoice.refresh_from_db()
    assert priced_invoice.status == Invoice.Status.PARTIAL


def test_create_payment_via_api_rejects_overpayment(api_client, priced_invoice, owner):
    api_client.force_authenticate(owner)
    api_client.post(PAYMENTS_URL, {"invoice": priced_invoice.pk, "amount": "100.00"})

    response = api_client.post(PAYMENTS_URL, {"invoice": priced_invoice.pk, "amount": "1.00"})

    assert response.status_code == 400


def test_create_payment_via_api_rejects_zero_amount(api_client, priced_invoice, owner):
    api_client.force_authenticate(owner)
    response = api_client.post(PAYMENTS_URL, {"invoice": priced_invoice.pk, "amount": "0"})
    assert response.status_code == 400


def test_list_payments_scoped_to_owner(api_client, priced_invoice, owner, other_employee):
    record_payment(priced_invoice, 10)
    api_client.force_authenticate(other_employee)
    response = api_client.get(PAYMENTS_URL)
    assert response.status_code == 200
    assert response.data["count"] == 0


def test_owner_can_list_own_invoice_payments(api_client, priced_invoice, owner):
    record_payment(priced_invoice, 10)
    api_client.force_authenticate(owner)
    response = api_client.get(PAYMENTS_URL)
    assert response.status_code == 200
    assert response.data["count"] == 1


def test_unauthenticated_denied(api_client, priced_invoice):
    response = api_client.post(PAYMENTS_URL, {"invoice": priced_invoice.pk, "amount": "10.00"})
    assert response.status_code == 401


def test_payment_update_not_allowed(api_client, priced_invoice, owner):
    api_client.force_authenticate(owner)
    transaction = record_payment(priced_invoice, 10)
    response = api_client.patch(_detail(PAYMENTS_URL, transaction.pk), {"amount": "20.00"})
    assert response.status_code == 405


def test_payment_soft_delete_not_allowed(api_client, priced_invoice, owner):
    api_client.force_authenticate(owner)
    transaction = record_payment(priced_invoice, 10)
    response = api_client.delete(_detail(PAYMENTS_URL, transaction.pk))
    assert response.status_code == 405


def test_invoice_detail_serializer_nests_payments(api_client, priced_invoice, owner):
    record_payment(priced_invoice, 10)
    api_client.force_authenticate(owner)
    response = api_client.get(_detail("/api/v1/sales/invoices/", priced_invoice.pk))
    assert response.status_code == 200
    assert len(response.data["payments"]) == 1
    assert response.data["amount_paid"] == "10.00"
    assert response.data["balance"] == "90.00"
