"""CP9/CP10: tests for apps/crm/permissions.py.

No new role-comparison logic exists in this app — these tests verify (1)
the re-exports are genuinely the same CP6 objects, and (2) CP6's
``IsOwnerOrSuperAdmin`` correctly resolves ownership for `Customer`/`Lead`
(via their own ``owner`` FK) and `ContactPerson`/`Address` (via the
``owner`` property delegating to ``customer.owner``), using the same
DummyRequest/DummyView, no-database pattern established in CP6-CP8.

CP10 note: ``test_unrelated_manager_denied_on_a_contact_they_do_not_own``
is the one exception — CP10 gave ``Customer``/``Lead`` (and, through
delegation, ``ContactPerson``/``Address``) a real ``manager_has_access()``
that consults ``apps.crm.services.managed_user_ids()``, which queries CP8's
``Team``/``Membership`` models. That single test therefore needs
``@pytest.mark.django_db`` now — everything else in this file still
short-circuits before reaching that hook (either resolved via ``owner``
directly, or denied earlier for not being a Manager at all) and remains
genuinely DB-free.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.crm import permissions as crm_permissions
from apps.crm.models import Address, ContactPerson, Customer, Lead

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


def test_reexported_classes_are_the_same_objects_as_accounts_permissions():
    assert crm_permissions.IsSuperAdmin is accounts_permissions.IsSuperAdmin
    assert crm_permissions.IsManager is accounts_permissions.IsManager
    assert crm_permissions.IsEmployee is accounts_permissions.IsEmployee
    assert crm_permissions.IsManagerOrSuperAdmin is accounts_permissions.IsManagerOrSuperAdmin
    assert crm_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin
    assert crm_permissions.ReadOnlyOrSuperAdmin is accounts_permissions.ReadOnlyOrSuperAdmin


def test_customer_owner_passes_is_owner_or_super_admin():
    owner = _user(User.Role.MANAGER, "owner@example.com", 1)
    customer = Customer(name="Globex")
    customer.owner = owner
    perm = crm_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(owner), DummyView(), customer) is True


def test_different_employee_denied_on_someone_elses_customer():
    owner = _user(User.Role.MANAGER, "owner@example.com", 1)
    other = _user(User.Role.EMPLOYEE, "other@example.com", 2)
    customer = Customer(name="Globex")
    customer.owner = owner
    perm = crm_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(other), DummyView(), customer) is False


def test_lead_owner_passes_is_owner_or_super_admin():
    owner = _user(User.Role.EMPLOYEE, "owner@example.com", 1)
    lead = Lead(company_name="Initech")
    lead.owner = owner
    perm = crm_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(owner), DummyView(), lead) is True


def test_super_admin_always_passes_regardless_of_ownership():
    admin = _user(User.Role.SUPER_ADMIN, "admin@example.com", 9)
    customer = Customer(name="Globex")  # no owner assigned
    perm = crm_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(admin), DummyView(), customer) is True


def test_contactperson_owner_resolved_through_customer():
    owner = _user(User.Role.MANAGER, "owner@example.com", 1)
    customer = Customer(name="Globex")
    customer.owner = owner
    contact = ContactPerson(customer=customer, first_name="Jane", last_name="Doe")
    perm = crm_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(owner), DummyView(), contact) is True


def test_address_owner_resolved_through_customer():
    owner = _user(User.Role.MANAGER, "owner@example.com", 1)
    customer = Customer(name="Globex")
    customer.owner = owner
    address = Address(customer=customer, line1="1 Main St", city="Springfield", country="USA")
    perm = crm_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(owner), DummyView(), address) is True


@pytest.mark.django_db
def test_unrelated_manager_denied_on_a_contact_they_do_not_own():
    owner = _user(User.Role.MANAGER, "owner@example.com", 1)
    other_manager = _user(User.Role.MANAGER, "other@example.com", 2)
    customer = Customer(name="Globex")
    customer.owner = owner
    contact = ContactPerson(customer=customer, first_name="Jane", last_name="Doe")
    perm = crm_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(other_manager), DummyView(), contact) is False
