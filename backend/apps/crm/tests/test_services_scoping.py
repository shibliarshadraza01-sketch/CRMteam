"""CP10: tests for apps/crm/services.py's ``managed_user_ids()``/
``scope_queryset_for_user()``, and the ``Customer``/``Lead
.manager_has_access()`` hooks that reuse them. All require a real database
— ``managed_user_ids()`` evaluates a real queryset (wraps it in ``set()``)
to compute team membership via CP8's ``Team``/``Membership`` models.
"""
import pytest

from apps.crm.models import Customer
from apps.crm.services import managed_user_ids, scope_queryset_for_user

pytestmark = pytest.mark.django_db


def test_managed_user_ids_includes_the_manager_themselves(manager):
    assert manager.id in managed_user_ids(manager)


def test_managed_user_ids_includes_team_members(manager, employee, managed_team):
    ids = managed_user_ids(manager)
    assert employee.id in ids


def test_managed_user_ids_excludes_unrelated_users(manager, other_employee, managed_team):
    ids = managed_user_ids(manager)
    assert other_employee.id not in ids


def test_managed_user_ids_for_manager_with_no_teams_is_just_themselves(manager):
    assert managed_user_ids(manager) == {manager.id}


# --------------------------------------------------------------------------
# scope_queryset_for_user()
# --------------------------------------------------------------------------


def test_scope_queryset_returns_none_for_unauthenticated():
    class Anonymous:
        is_authenticated = False

    result = scope_queryset_for_user(Customer.objects.all(), Anonymous())
    assert list(result) == []


def test_scope_queryset_returns_everything_for_super_admin(organization, super_admin, employee, other_employee):
    Customer.objects.create(organization=organization, name="A", slug="a", owner=employee)
    Customer.objects.create(organization=organization, name="B", slug="b", owner=other_employee)

    result = scope_queryset_for_user(Customer.objects.all(), super_admin)

    assert result.count() == 2


def test_scope_queryset_returns_only_own_records_for_employee(organization, employee, other_employee):
    mine = Customer.objects.create(organization=organization, name="Mine", slug="mine", owner=employee)
    Customer.objects.create(organization=organization, name="Theirs", slug="theirs", owner=other_employee)

    result = scope_queryset_for_user(Customer.objects.all(), employee)

    assert list(result) == [mine]


def test_scope_queryset_returns_own_and_team_records_for_manager(organization, manager, employee, other_employee, managed_team):
    mine = Customer.objects.create(organization=organization, name="Mine", slug="mine", owner=manager)
    team_member = Customer.objects.create(organization=organization, name="Team", slug="team", owner=employee)
    Customer.objects.create(organization=organization, name="Unrelated", slug="unrelated", owner=other_employee)

    result = scope_queryset_for_user(Customer.objects.all(), manager)

    assert set(result) == {mine, team_member}


def test_scope_queryset_supports_owner_field_traversal(organization, employee, other_employee, customer):
    from apps.crm.models import ContactPerson

    customer.owner = employee
    customer.save()
    mine = ContactPerson.objects.create(customer=customer, first_name="Jane", last_name="Doe")

    other_customer = Customer.objects.create(organization=organization, name="Other", slug="other", owner=other_employee)
    ContactPerson.objects.create(customer=other_customer, first_name="John", last_name="Smith")

    result = scope_queryset_for_user(ContactPerson.objects.all(), employee, owner_field="customer__owner")

    assert list(result) == [mine]


# --------------------------------------------------------------------------
# Customer/Lead.manager_has_access()
# --------------------------------------------------------------------------


def test_customer_manager_has_access_true_for_team_manager(organization, manager, employee, managed_team):
    customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs", owner=employee)
    assert customer.manager_has_access(manager) is True


def test_customer_manager_has_access_false_for_unrelated_manager(organization, employee, django_user_model):
    unrelated = django_user_model.objects.create_user(
        email="unrelated@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs", owner=employee)
    assert customer.manager_has_access(unrelated) is False


def test_customer_manager_has_access_false_with_no_owner(organization, manager):
    customer = Customer.objects.create(organization=organization, name="Orphan", slug="orphan")
    assert customer.manager_has_access(manager) is False
