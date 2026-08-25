"""Final internet-facing security audit: regression tests for a real
BOLA/IDOR vulnerability found and fixed in this pass.

Root cause: every "child resource attaches to an existing parent
identified by a client-supplied ID" ``perform_create()`` (ContactPerson/
Address -> Customer, Quote/QuoteItem -> Customer/Quote, Invoice/
InvoiceItem/PaymentTransaction -> Customer/Invoice, DashboardWidget ->
Dashboard/Report, WorkflowAction -> Workflow, Reminder -> Task/Event,
APIKey/WebhookEndpoint -> Integration) popped the parent object out of
``validated_data`` and used it immediately, with no check that the
requesting user could actually access that parent. DRF's permission
classes only ever run ``has_object_permission()`` against an object
``get_object()`` fetched — a POST to a list endpoint has no object yet,
so the parent PK referenced inside the create payload was validated only
by the serializer field's (unscoped) queryset, never by ownership. Any
authenticated user could attach a fabricated child record — a fake
contact, an inflated invoice line item, a payment against someone else's
invoice — to ANY other user's parent object just by guessing/enumerating
its ID.

Fixed by ``apps.accounts.permissions.assert_object_accessible()``, called
immediately after popping the parent, reusing the exact same
``IsOwnerOrSuperAdmin.has_object_permission()`` rule already enforced for
retrieve/update/destroy — so create-time and read/update-time access
control can never disagree.

This file exercises the two vulnerabilities found via live manual
testing (payment against another user's invoice; a fabricated invoice
line item) plus the same pattern on ``ContactPerson``, all fixed by the
identical one-line call.
"""
import pytest
from rest_framework.test import APIClient

from apps.crm.models import Customer
from apps.organization.models import Organization
from apps.sales.models import Invoice

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def organization(db):
    return Organization.objects.create(name="BOLA Test Org", slug="bola-test-org")


@pytest.fixture
def employee_a(db, django_user_model):
    return django_user_model.objects.create_user(
        email="bola-a@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def employee_b(db, django_user_model):
    return django_user_model.objects.create_user(
        email="bola-b@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="bola-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def customer_a(db, organization, employee_a):
    """Owned by employee_a — employee_b must never be able to attach a
    child record to this customer.
    """
    return Customer.objects.create(organization=organization, name="Customer A", slug="customer-a", owner=employee_a)


@pytest.fixture
def invoice_a(db, customer_a, employee_a):
    return Invoice.objects.create(customer=customer_a, invoice_number="INV-BOLA-A", owner=employee_a, total=100)


def test_employee_cannot_add_contact_to_another_employees_customer(api_client, customer_a, employee_b):
    api_client.force_authenticate(employee_b)
    response = api_client.post(
        "/api/v1/crm/contacts/", {"customer": customer_a.pk, "first_name": "Injected", "last_name": "Contact"}
    )
    assert response.status_code == 404
    assert customer_a.contacts.count() == 0


def test_employee_cannot_add_address_to_another_employees_customer(api_client, customer_a, employee_b):
    api_client.force_authenticate(employee_b)
    response = api_client.post(
        "/api/v1/crm/addresses/",
        {"customer": customer_a.pk, "address_type": "BILLING", "line1": "1 Fake St", "city": "Faketown", "country": "US"},
    )
    assert response.status_code == 404


def test_employee_cannot_create_invoice_against_another_employees_customer(api_client, customer_a, employee_b):
    # Revenue/Payments audit pass: Invoice writes are Super-Admin-only now
    # (apps.sales.views.InvoiceViewSet), so a plain Employee is refused at
    # the permission layer (403) before ever reaching the BOLA object check
    # this test originally exercised (which would have been a 404) — an
    # even stronger guarantee than before: an Employee can no longer
    # create ANY invoice, their own or someone else's.
    api_client.force_authenticate(employee_b)
    response = api_client.post(
        "/api/v1/sales/invoices/", {"customer": customer_a.pk, "invoice_number": "INV-STOLEN"}
    )
    assert response.status_code == 403


def test_employee_cannot_add_line_item_to_another_employees_invoice(api_client, invoice_a, employee_b):
    """Live-verified vulnerability: employee_b could previously inflate
    employee_a's invoice total by injecting a fake line item.

    Revenue/Payments audit pass: now refused even earlier, at the
    permission layer (403) — an Employee cannot add a line item to ANY
    invoice, not just someone else's.
    """
    api_client.force_authenticate(employee_b)
    response = api_client.post(
        "/api/v1/sales/invoice-items/",
        {"invoice": invoice_a.pk, "product_name": "Injected item", "quantity": 1, "unit_price": "999.00"},
    )
    assert response.status_code == 403
    invoice_a.refresh_from_db()
    assert invoice_a.total == 100
    assert invoice_a.items.count() == 0


def test_employee_cannot_record_payment_against_another_employees_invoice(api_client, invoice_a, employee_b):
    """Live-verified vulnerability: employee_b could previously record a
    real payment transaction against employee_a's invoice.

    Revenue/Payments audit pass: now refused even earlier, at the
    permission layer (403) — an Employee cannot record a payment against
    ANY invoice, not just someone else's.
    """
    api_client.force_authenticate(employee_b)
    response = api_client.post(
        "/api/v1/sales/payments/", {"invoice": invoice_a.pk, "amount": "5.00"}
    )
    assert response.status_code == 403
    invoice_a.refresh_from_db()
    assert invoice_a.amount_paid == 0
    assert invoice_a.payments.count() == 0


def test_owner_employee_can_no_longer_add_line_item_or_record_payment(api_client, invoice_a, employee_a):
    """Revenue/Payments audit pass superseded the original BOLA fix's
    "the legitimate owner is still allowed" guarantee: ownership alone no
    longer grants write access to a real revenue record — only a Super
    Admin may create/edit an invoice line item or record a payment, even
    against an invoice the requesting Employee genuinely owns.
    """
    api_client.force_authenticate(employee_a)
    item_response = api_client.post(
        "/api/v1/sales/invoice-items/",
        {"invoice": invoice_a.pk, "product_name": "Legit item", "quantity": 1, "unit_price": "10.00"},
    )
    assert item_response.status_code == 403

    payment_response = api_client.post(
        "/api/v1/sales/payments/", {"invoice": invoice_a.pk, "amount": "5.00"}
    )
    assert payment_response.status_code == 403


def test_super_admin_can_still_add_line_item_and_record_payment(api_client, invoice_a, super_admin):
    """The one role revenue/payment writes remain available to at all —
    same requests the old "owner can still..."/"manager can still..."
    tests exercised, now only reachable by a Super Admin."""
    api_client.force_authenticate(super_admin)
    item_response = api_client.post(
        "/api/v1/sales/invoice-items/",
        {"invoice": invoice_a.pk, "product_name": "Legit item", "quantity": 1, "unit_price": "10.00"},
    )
    assert item_response.status_code == 201

    payment_response = api_client.post(
        "/api/v1/sales/payments/", {"invoice": invoice_a.pk, "amount": "5.00"}
    )
    assert payment_response.status_code == 201


def test_manager_cannot_add_line_item_even_to_managed_employees_invoice(api_client, invoice_a, employee_a, organization):
    """Revenue/Payments audit pass: "a Manager can act on their team's
    records" — true everywhere else in this project — explicitly does NOT
    extend to revenue. A Manager managing employee_a's team must still be
    refused, exactly like any other non-Super-Admin.
    """
    from apps.organization.models import Department, Membership, Team

    User = type(employee_a)
    manager = User.objects.create_user(email="bola-manager@example.com", password="x", role=User.Role.MANAGER)
    department = Department.objects.create(organization=organization, name="BOLA Dept")
    team = Team.objects.create(department=department, name="BOLA Team", manager=manager)
    Membership.objects.create(user=employee_a, team=team)

    api_client.force_authenticate(manager)
    response = api_client.post(
        "/api/v1/sales/invoice-items/",
        {"invoice": invoice_a.pk, "product_name": "Manager-added item", "quantity": 1, "unit_price": "10.00"},
    )
    assert response.status_code == 403
