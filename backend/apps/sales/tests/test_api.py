"""CP12: end-to-end tests for the sales API — CRUD, stage/payment
transitions, search, filtering, ordering. Requires a real database.
"""
import pytest

from apps.sales.models import Invoice, Quote

pytestmark = pytest.mark.django_db

QUOTES_URL = "/api/v1/sales/quotes/"
INVOICES_URL = "/api/v1/sales/invoices/"
QUOTE_ITEMS_URL = "/api/v1/sales/quote-items/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# Quote CRUD
# --------------------------------------------------------------------------


def test_create_quote(api_client, customer, manager):
    api_client.force_authenticate(manager)

    response = api_client.post(QUOTES_URL, {"customer": customer.pk, "quote_number": "Q-API-1"})

    assert response.status_code == 201
    q = Quote.objects.get(pk=response.data["id"])
    assert q.owner_id == manager.id


def test_list_quotes_returns_only_active_rows(api_client, super_admin, customer):
    visible = Quote.objects.create(customer=customer, quote_number="Q-VIS")
    deleted = Quote.objects.create(customer=customer, quote_number="Q-DEL")
    deleted.soft_delete()
    api_client.force_authenticate(super_admin)

    response = api_client.get(QUOTES_URL)

    numbers = {row["quote_number"] for row in response.data["results"]}
    assert numbers == {"Q-VIS"}


def test_retrieve_quote_uses_detail_serializer(api_client, quote, owner):
    api_client.force_authenticate(owner)
    response = api_client.get(_detail(QUOTES_URL, quote.pk))
    assert response.status_code == 200
    assert "customer_name" in response.data
    assert "items" in response.data


def test_patch_quote(api_client, quote, owner):
    api_client.force_authenticate(owner)
    response = api_client.patch(_detail(QUOTES_URL, quote.pk), {"notes": "Updated notes"})
    assert response.status_code == 200
    quote.refresh_from_db()
    assert quote.notes == "Updated notes"


def test_put_quote_not_allowed(api_client, quote, owner):
    api_client.force_authenticate(owner)
    response = api_client.put(_detail(QUOTES_URL, quote.pk), {"quote_number": "X"})
    assert response.status_code == 405


def test_patching_status_directly_is_ignored_since_read_only(api_client, quote, owner):
    api_client.force_authenticate(owner)
    response = api_client.patch(_detail(QUOTES_URL, quote.pk), {"status": "APPROVED"})
    assert response.status_code == 200
    quote.refresh_from_db()
    assert quote.status == Quote.Status.DRAFT  # unchanged — status is read-only


def test_delete_quote_soft_deletes(api_client, quote, owner):
    api_client.force_authenticate(owner)
    response = api_client.delete(_detail(QUOTES_URL, quote.pk))
    assert response.status_code == 204
    quote.refresh_from_db()
    assert quote.is_deleted is True


def test_employee_cannot_retrieve_someone_elses_quote(api_client, organization, employee, other_employee):
    from apps.crm.models import Customer

    theirs_customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs-sales-api", owner=other_employee)
    theirs = Quote.objects.create(customer=theirs_customer, quote_number="Q-THEIRS", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(_detail(QUOTES_URL, theirs.pk))
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Quote stage transitions
# --------------------------------------------------------------------------


def test_submit_action(api_client, quote, owner):
    api_client.force_authenticate(owner)
    response = api_client.post(f"{_detail(QUOTES_URL, quote.pk)}submit/")
    assert response.status_code == 200
    quote.refresh_from_db()
    assert quote.status == Quote.Status.SUBMITTED


def test_approve_action_rejects_draft(api_client, quote, owner):
    api_client.force_authenticate(owner)
    response = api_client.post(f"{_detail(QUOTES_URL, quote.pk)}approve/")
    assert response.status_code == 400


def test_approve_action(api_client, quote, owner):
    api_client.force_authenticate(owner)
    api_client.post(f"{_detail(QUOTES_URL, quote.pk)}submit/")

    response = api_client.post(f"{_detail(QUOTES_URL, quote.pk)}approve/")

    assert response.status_code == 200
    quote.refresh_from_db()
    assert quote.status == Quote.Status.APPROVED
    assert quote.approved_by_id == owner.id


def test_reject_action_rejects_approved(api_client, quote, owner):
    api_client.force_authenticate(owner)
    api_client.post(f"{_detail(QUOTES_URL, quote.pk)}submit/")
    api_client.post(f"{_detail(QUOTES_URL, quote.pk)}approve/")

    response = api_client.post(f"{_detail(QUOTES_URL, quote.pk)}reject/")

    assert response.status_code == 400


def test_convert_action_requires_approved(api_client, quote, owner):
    api_client.force_authenticate(owner)
    response = api_client.post(f"{_detail(QUOTES_URL, quote.pk)}convert/", {"invoice_number": "INV-C1"})
    assert response.status_code == 400


def test_convert_action_creates_invoice(api_client, quote, owner):
    api_client.force_authenticate(owner)
    api_client.post(f"{_detail(QUOTES_URL, quote.pk)}submit/")
    api_client.post(f"{_detail(QUOTES_URL, quote.pk)}approve/")

    response = api_client.post(f"{_detail(QUOTES_URL, quote.pk)}convert/", {"invoice_number": "INV-C2"})

    assert response.status_code == 200
    assert Invoice.objects.filter(invoice_number="INV-C2").exists()
    quote.refresh_from_db()
    assert quote.status == Quote.Status.CONVERTED


def test_convert_action_requires_invoice_number(api_client, quote, owner):
    api_client.force_authenticate(owner)
    api_client.post(f"{_detail(QUOTES_URL, quote.pk)}submit/")
    api_client.post(f"{_detail(QUOTES_URL, quote.pk)}approve/")

    response = api_client.post(f"{_detail(QUOTES_URL, quote.pk)}convert/")

    assert response.status_code == 400


def test_convert_action_idempotent(api_client, quote, owner):
    api_client.force_authenticate(owner)
    api_client.post(f"{_detail(QUOTES_URL, quote.pk)}submit/")
    api_client.post(f"{_detail(QUOTES_URL, quote.pk)}approve/")
    first = api_client.post(f"{_detail(QUOTES_URL, quote.pk)}convert/", {"invoice_number": "INV-C3"})

    second = api_client.post(f"{_detail(QUOTES_URL, quote.pk)}convert/", {"invoice_number": "IGNORED"})

    assert second.status_code == 200
    assert second.data["id"] == first.data["id"]


def test_stage_transition_requires_ownership(api_client, organization, employee, other_employee):
    from apps.crm.models import Customer

    theirs_customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs-stage-sales", owner=other_employee)
    theirs = Quote.objects.create(customer=theirs_customer, quote_number="Q-STAGE", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.post(f"{_detail(QUOTES_URL, theirs.pk)}submit/")
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Invoice CRUD + payment lifecycle
# --------------------------------------------------------------------------


def test_create_invoice(api_client, customer, manager):
    api_client.force_authenticate(manager)
    response = api_client.post(INVOICES_URL, {"customer": customer.pk, "invoice_number": "INV-API-1"})
    assert response.status_code == 201


def test_retrieve_invoice_uses_detail_serializer(api_client, invoice, owner):
    api_client.force_authenticate(owner)
    response = api_client.get(_detail(INVOICES_URL, invoice.pk))
    assert "customer_name" in response.data
    assert "items" in response.data


def test_mark_paid_action(api_client, invoice, owner):
    api_client.force_authenticate(owner)
    response = api_client.post(f"{_detail(INVOICES_URL, invoice.pk)}mark-paid/")
    assert response.status_code == 200
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID


def test_cancel_action(api_client, invoice, owner):
    api_client.force_authenticate(owner)
    response = api_client.post(f"{_detail(INVOICES_URL, invoice.pk)}cancel/")
    assert response.status_code == 200
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.CANCELLED


def test_cancel_action_rejects_paid(api_client, invoice, owner):
    api_client.force_authenticate(owner)
    api_client.post(f"{_detail(INVOICES_URL, invoice.pk)}mark-paid/")

    response = api_client.post(f"{_detail(INVOICES_URL, invoice.pk)}cancel/")

    assert response.status_code == 400


def test_mark_paid_action_rejects_cancelled(api_client, invoice, owner):
    api_client.force_authenticate(owner)
    api_client.post(f"{_detail(INVOICES_URL, invoice.pk)}cancel/")

    response = api_client.post(f"{_detail(INVOICES_URL, invoice.pk)}mark-paid/")

    assert response.status_code == 400


# --------------------------------------------------------------------------
# QuoteItem via its own resource
# --------------------------------------------------------------------------


def test_create_quote_item_via_api_recalculates_totals(api_client, quote, owner):
    api_client.force_authenticate(owner)

    response = api_client.post(
        QUOTE_ITEMS_URL, {"quote": quote.pk, "product_name": "Widget", "quantity": "2", "unit_price": "10.00"}
    )

    assert response.status_code == 201
    quote.refresh_from_db()
    assert quote.subtotal == 20


# --------------------------------------------------------------------------
# Search / filter / ordering
# --------------------------------------------------------------------------


def test_search_quotes_by_quote_number(api_client, super_admin, customer):
    Quote.objects.create(customer=customer, quote_number="Q-ROCKET")
    Quote.objects.create(customer=customer, quote_number="Q-OTHER")
    api_client.force_authenticate(super_admin)

    response = api_client.get(QUOTES_URL, {"search": "ROCKET"})
    numbers = {row["quote_number"] for row in response.data["results"]}
    assert numbers == {"Q-ROCKET"}


def test_filter_quotes_by_status(api_client, super_admin, customer):
    Quote.objects.create(customer=customer, quote_number="Q-A", status=Quote.Status.DRAFT)
    Quote.objects.create(customer=customer, quote_number="Q-B", status=Quote.Status.SUBMITTED)
    api_client.force_authenticate(super_admin)

    response = api_client.get(QUOTES_URL, {"status": "SUBMITTED"})
    numbers = {row["quote_number"] for row in response.data["results"]}
    assert numbers == {"Q-B"}


def test_order_invoices_by_total(api_client, super_admin, customer):
    Invoice.objects.create(customer=customer, invoice_number="INV-SMALL", total=10)
    Invoice.objects.create(customer=customer, invoice_number="INV-BIG", total=9000)
    api_client.force_authenticate(super_admin)

    response = api_client.get(INVOICES_URL, {"ordering": "total"})
    numbers = [row["invoice_number"] for row in response.data["results"]]
    assert numbers == ["INV-SMALL", "INV-BIG"]
