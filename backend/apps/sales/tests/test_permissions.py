"""CP12: tests confirming CP6's ``IsOwnerOrSuperAdmin`` (unchanged) works
correctly against ``Quote``/``Invoice``/``QuoteItem``/``InvoiceItem`` with
zero new permission logic.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.crm.models import Customer
from apps.sales import permissions as sales_permissions
from apps.accounts import permissions as accounts_permissions
from apps.sales.models import Invoice, InvoiceItem, Quote, QuoteItem
from apps.sales.permissions import IsOwnerOrSuperAdmin

User = get_user_model()


class DummyRequest:
    def __init__(self, user):
        self.user = user


class DummyView:
    pass


def _user(role, email, pk):
    user = User(email=email, role=role)
    user.pk = pk
    return user


# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_reexported_classes_are_the_same_objects_as_accounts_permissions():
    assert sales_permissions.IsSuperAdmin is accounts_permissions.IsSuperAdmin
    assert sales_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin
    assert sales_permissions.IsManagerOrSuperAdmin is accounts_permissions.IsManagerOrSuperAdmin


def test_quote_owner_passes():
    owner = _user(User.Role.EMPLOYEE, "owner@example.com", 1)
    quote = Quote(quote_number="Q-1", customer=Customer(name="Globex"), owner=owner)
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(owner), DummyView(), quote) is True


def test_different_employee_denied_on_someone_elses_quote():
    owner = _user(User.Role.EMPLOYEE, "owner@example.com", 1)
    other = _user(User.Role.EMPLOYEE, "other@example.com", 2)
    quote = Quote(quote_number="Q-1", customer=Customer(name="Globex"), owner=owner)
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(other), DummyView(), quote) is False


def test_super_admin_always_passes():
    admin = _user(User.Role.SUPER_ADMIN, "admin@example.com", 9)
    quote = Quote(quote_number="Q-1", customer=Customer(name="Globex"))
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(admin), DummyView(), quote) is True


def test_quote_item_and_invoice_item_owner_resolved_through_parent():
    owner = _user(User.Role.EMPLOYEE, "owner@example.com", 1)
    quote = Quote(quote_number="Q-1", customer=Customer(name="Globex"), owner=owner)
    invoice = Invoice(invoice_number="INV-1", customer=Customer(name="Globex"), owner=owner)
    quote_item = QuoteItem(quote=quote, product_name="Widget")
    invoice_item = InvoiceItem(invoice=invoice, product_name="Widget")
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(owner), DummyView(), quote_item) is True
    assert perm.has_object_permission(DummyRequest(owner), DummyView(), invoice_item) is True


# --------------------------------------------------------------------------
# Requires database — Manager-not-owner path (queries Team/Membership)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_team_manager_passes_via_manager_has_access(organization, manager, employee, managed_team, customer):
    customer.owner = employee
    customer.save()
    quote = Quote.objects.create(customer=customer, quote_number="Q-PERM", owner=employee)
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(manager), DummyView(), quote) is True


@pytest.mark.django_db
def test_unrelated_manager_denied(customer, employee, django_user_model):
    unrelated = django_user_model.objects.create_user(
        email="unrelated-sales-perm@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    invoice = Invoice.objects.create(customer=customer, invoice_number="INV-PERM", owner=employee)
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(unrelated), DummyView(), invoice) is False
