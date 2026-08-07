"""CP9: tests for Customer/Lead managers and querysets."""
import pytest

from apps.crm.models import Customer, Lead
from apps.organization.models import Organization

# --------------------------------------------------------------------------
# No database required — queryset structure
# --------------------------------------------------------------------------


def test_customer_manager_has_expected_helpers():
    for helper in ("active", "by_owner", "by_status", "deleted", "hard_delete", "restore"):
        assert hasattr(Customer.objects, helper)


def test_customer_active_filters_is_deleted_and_is_active_without_hitting_db():
    queryset = Customer.objects.active()
    where_sql = str(queryset.query.where)
    assert "is_deleted" in where_sql
    assert "is_active" in where_sql


def test_customer_by_owner_filters_without_hitting_db():
    queryset = Customer.objects.by_owner(user=None)
    assert len(queryset.query.where) > 0


def test_customer_by_status_filters_without_hitting_db():
    queryset = Customer.objects.by_status(Customer.Status.ACTIVE)
    assert len(queryset.query.where) > 0


def test_lead_manager_has_expected_helpers():
    for helper in ("by_owner", "by_status", "converted", "unconverted", "deleted", "restore"):
        assert hasattr(Lead.objects, helper)


def test_lead_converted_and_unconverted_are_opposite_filters():
    converted_sql = str(Lead.objects.converted().query.where)
    unconverted_sql = str(Lead.objects.unconverted().query.where)
    assert "converted_customer" in converted_sql
    assert "converted_customer" in unconverted_sql
    assert converted_sql != unconverted_sql


def test_lead_active_objects_does_not_filter_by_is_active_field():
    # Lead has no is_active field (unlike Customer) — active_objects means
    # "not soft-deleted" only.
    queryset = Lead.active_objects.all()
    where_sql = str(queryset.query.where)
    assert "is_deleted" in where_sql
    assert "is_active" not in where_sql


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_customer_active_excludes_inactive_and_deleted(organization):
    active = Customer.objects.create(organization=organization, name="Active Co", slug="active-co")
    inactive = Customer.objects.create(organization=organization, name="Inactive Co", slug="inactive-co", is_active=False)
    deleted = Customer.objects.create(organization=organization, name="Deleted Co", slug="deleted-co")
    deleted.soft_delete()

    names = set(Customer.active_objects.values_list("name", flat=True))

    assert names == {"Active Co"}


@pytest.mark.django_db
def test_customer_by_owner_and_by_status(organization, owner):
    Customer.objects.create(organization=organization, name="Owned", slug="owned", owner=owner, status=Customer.Status.ACTIVE)
    Customer.objects.create(organization=organization, name="Unowned", slug="unowned", status=Customer.Status.PROSPECT)

    assert Customer.objects.by_owner(owner).count() == 1
    assert Customer.objects.by_status(Customer.Status.ACTIVE).count() == 1


@pytest.mark.django_db
def test_lead_converted_and_unconverted_querysets(customer):
    converted = Lead.objects.create(company_name="A", contact_name="A", converted_customer=customer, status=Lead.Status.CONVERTED)
    unconverted = Lead.objects.create(company_name="B", contact_name="B")

    assert list(Lead.objects.converted()) == [converted]
    assert list(Lead.objects.unconverted()) == [unconverted]


@pytest.mark.django_db
def test_lead_by_owner_and_by_status(owner):
    Lead.objects.create(company_name="A", contact_name="A", owner=owner, status=Lead.Status.QUALIFIED)
    Lead.objects.create(company_name="B", contact_name="B", status=Lead.Status.NEW)

    assert Lead.objects.by_owner(owner).count() == 1
    assert Lead.objects.by_status(Lead.Status.QUALIFIED).count() == 1
