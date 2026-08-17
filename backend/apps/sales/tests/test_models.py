"""CP12: tests for apps/sales/models.py."""
import pytest
from django.contrib.auth import get_user_model
from django.db import models

from apps.crm.models import Customer
from apps.sales.models import Invoice, InvoiceItem, Quote, QuoteItem

User = get_user_model()


def _unsaved_user(role=User.Role.EMPLOYEE, email="user@example.com"):
    return User(email=email, role=role)


# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_quote_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in Quote._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_quote_number_is_unique():
    assert Quote._meta.get_field("quote_number").unique is True


def test_quote_status_choices_and_default():
    values = {c.value for c in Quote.Status}
    assert values == {"DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "CONVERTED"}
    assert Quote._meta.get_field("status").default == Quote.Status.DRAFT


def test_quote_fk_related_names():
    assert Quote._meta.get_field("customer").remote_field.related_name == "quotes"
    assert Quote._meta.get_field("opportunity").remote_field.related_name == "quotes"
    assert Quote._meta.get_field("owner").remote_field.related_name == "owned_quotes"
    assert Quote._meta.get_field("approved_by").remote_field.related_name == "approved_quotes"
    assert Quote._meta.get_field("converted_invoice").remote_field.related_name == "source_quote"


def test_quote_money_fields_are_decimal():
    for name in ("subtotal", "tax", "total"):
        assert isinstance(Quote._meta.get_field(name), models.DecimalField)


def test_quote_str_returns_quote_number():
    assert str(Quote(quote_number="Q-0099")) == "Q-0099"


def test_quote_manager_has_access_false_with_no_owner():
    quote = Quote(quote_number="Q-1", customer=Customer(name="Globex"))
    manager = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    assert quote.manager_has_access(manager) is False


def test_quoteitem_fk_related_name():
    assert QuoteItem._meta.get_field("quote").remote_field.related_name == "items"
    assert QuoteItem._meta.get_field("quote").remote_field.on_delete is models.CASCADE


def test_quoteitem_str_includes_product_and_quantity():
    item = QuoteItem(product_name="Widget", quantity=3)
    assert str(item) == "Widget x3"


def test_quoteitem_owner_delegates_to_quote():
    owner = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    quote = Quote(quote_number="Q-1", customer=Customer(name="Globex"), owner=owner)
    item = QuoteItem(quote=quote, product_name="Widget")
    assert item.owner is owner


def test_invoice_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in Invoice._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_invoice_number_is_unique():
    assert Invoice._meta.get_field("invoice_number").unique is True


def test_invoice_status_choices_and_default():
    values = {c.value for c in Invoice.Status}
    assert values == {"DRAFT", "SENT", "PARTIAL", "PAID", "CANCELLED"}
    assert Invoice._meta.get_field("status").default == Invoice.Status.DRAFT


def test_invoice_fk_related_names():
    assert Invoice._meta.get_field("customer").remote_field.related_name == "invoices"
    assert Invoice._meta.get_field("quote").remote_field.related_name == "invoices"
    assert Invoice._meta.get_field("owner").remote_field.related_name == "owned_invoices"


def test_invoice_str_returns_invoice_number():
    assert str(Invoice(invoice_number="INV-0099")) == "INV-0099"


def test_invoiceitem_fk_related_name():
    assert InvoiceItem._meta.get_field("invoice").remote_field.related_name == "items"


def test_invoiceitem_owner_delegates_to_invoice():
    owner = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    invoice = Invoice(invoice_number="INV-1", customer=Customer(name="Globex"), owner=owner)
    item = InvoiceItem(invoice=invoice, product_name="Widget")
    assert item.owner is owner


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_quote_create_and_retrieve(customer, owner):
    quote = Quote.objects.create(customer=customer, quote_number="Q-100", owner=owner)
    fetched = Quote.objects.get(pk=quote.pk)
    assert fetched.status == Quote.Status.DRAFT


@pytest.mark.django_db
def test_quote_number_uniqueness_enforced(customer):
    from django.db import IntegrityError

    Quote.objects.create(customer=customer, quote_number="Q-DUP")
    with pytest.raises(IntegrityError):
        Quote.objects.create(customer=customer, quote_number="Q-DUP")


@pytest.mark.django_db
def test_deleting_customer_cascades_to_quotes_and_invoices(customer):
    quote = Quote.objects.create(customer=customer, quote_number="Q-200")
    invoice = Invoice.objects.create(customer=customer, invoice_number="INV-200")
    customer.delete()
    assert not Quote.objects.filter(pk=quote.pk).exists()
    assert not Invoice.objects.filter(pk=invoice.pk).exists()


@pytest.mark.django_db
def test_deleting_quote_cascades_to_items(quote):
    item = QuoteItem.objects.create(quote=quote, product_name="Widget", quantity=1, unit_price=10)
    quote.delete()
    assert not QuoteItem.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_deleting_invoice_cascades_to_items(invoice):
    item = InvoiceItem.objects.create(invoice=invoice, product_name="Widget", quantity=1, unit_price=10)
    invoice.delete()
    assert not InvoiceItem.objects.filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_deleting_owner_sets_null_not_cascade(quote, owner):
    quote.owner = owner
    quote.save()
    owner.delete()
    quote.refresh_from_db()
    assert quote.owner_id is None


@pytest.mark.django_db
def test_quote_and_invoice_are_linked_after_conversion(approved_quote):
    from apps.sales.services import convert_quote_to_invoice

    invoice = convert_quote_to_invoice(approved_quote, "INV-LINK")

    approved_quote.refresh_from_db()
    assert approved_quote.converted_invoice_id == invoice.id
    assert invoice.quote_id == approved_quote.id


@pytest.mark.django_db
def test_quote_manager_has_access_true_for_team_manager(organization, manager, employee, managed_team, customer):
    customer.owner = employee
    customer.save()
    quote = Quote.objects.create(customer=customer, quote_number="Q-MGR", owner=employee)
    assert quote.manager_has_access(manager) is True


@pytest.mark.django_db
def test_invoice_manager_has_access_false_for_unrelated_manager(customer, employee, django_user_model):
    unrelated = django_user_model.objects.create_user(
        email="unrelated-sales@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    invoice = Invoice.objects.create(customer=customer, invoice_number="INV-MGR", owner=employee)
    assert invoice.manager_has_access(unrelated) is False
