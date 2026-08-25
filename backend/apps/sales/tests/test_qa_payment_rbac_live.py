"""QA acceptance re-check: live end-to-end confirmation that Employee and
Manager cannot write payments/invoices via the real DRF endpoints, and that
Super Admin can, plus that recording a second partial payment aggregates
correctly (1000 total -> 400 paid -> 600 remaining -> +200 -> 600 paid /
400 remaining), exactly matching the QA acceptance script.
"""
import pytest
from rest_framework.test import APIClient

from apps.sales.models import Invoice

pytestmark = pytest.mark.django_db

INVOICES_URL = "/api/v1/sales/invoices/"
PAYMENTS_URL = "/api/v1/sales/payments/"


def _client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def test_employee_and_manager_cannot_write_payments_or_invoices(employee, manager, super_admin, customer):
    invoice = Invoice.objects.create(customer=customer, invoice_number="QA-RBAC-0001", owner=super_admin, total=1000)

    for user in (employee, manager):
        c = _client(user)
        r = c.post(INVOICES_URL, {"customer": str(customer.pk), "invoice_number": "QA-X", "total": "50"}, format="json")
        assert r.status_code == 403, (user, r.status_code, r.data)

        r = c.patch(f"{INVOICES_URL}{invoice.pk}/", {"total": "5"}, format="json")
        assert r.status_code == 403, (user, r.status_code, r.data)

        r = c.delete(f"{INVOICES_URL}{invoice.pk}/")
        assert r.status_code == 403, (user, r.status_code, r.data)

        r = c.post(PAYMENTS_URL, {"invoice": str(invoice.pk), "amount": "100"}, format="json")
        assert r.status_code == 403, (user, r.status_code, r.data)

    invoice.delete()


def test_super_admin_partial_payment_aggregation_matches_spec(super_admin, customer):
    invoice = Invoice.objects.create(customer=customer, invoice_number="QA-AGG-0001", owner=super_admin, total=1000)
    c = _client(super_admin)

    r = c.post(PAYMENTS_URL, {"invoice": str(invoice.pk), "amount": "400"}, format="json")
    assert r.status_code == 201, r.data
    invoice.refresh_from_db()
    assert invoice.amount_paid == 400
    assert invoice.balance == 600

    r = c.post(PAYMENTS_URL, {"invoice": str(invoice.pk), "amount": "200"}, format="json")
    assert r.status_code == 201, r.data
    invoice.refresh_from_db()
    assert invoice.amount_paid == 600
    assert invoice.balance == 400

    invoice.delete()
