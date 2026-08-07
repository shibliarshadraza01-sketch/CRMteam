"""CP11: tests for apps/crm/filters.py's OpportunityFilterSet."""
import pytest

from apps.crm.filters import OpportunityFilterSet
from apps.crm.opportunities import Opportunity

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_filterset_declares_spec_fields():
    assert set(OpportunityFilterSet.Meta.fields) == {"stage", "owner", "customer"}


def test_filterset_declares_closed_and_won_aliases():
    assert "closed" in OpportunityFilterSet.declared_filters
    assert "won" in OpportunityFilterSet.declared_filters
    assert OpportunityFilterSet.declared_filters["closed"].field_name == "is_closed"
    assert OpportunityFilterSet.declared_filters["won"].field_name == "is_won"


def test_filterset_declares_date_range_filters():
    for name in ("expected_close_date_from", "expected_close_date_to", "actual_close_date_from", "actual_close_date_to"):
        assert name in OpportunityFilterSet.declared_filters


def test_filterset_declares_value_range_filters():
    assert "value_min" in OpportunityFilterSet.declared_filters
    assert "value_max" in OpportunityFilterSet.declared_filters
    assert OpportunityFilterSet.declared_filters["value_min"].lookup_expr == "gte"
    assert OpportunityFilterSet.declared_filters["value_max"].lookup_expr == "lte"


def test_closed_filter_builds_query_without_hitting_db():
    filterset = OpportunityFilterSet(data={"closed": "true"}, queryset=Opportunity.objects.all())
    assert filterset.is_valid()
    qs = filterset.qs
    assert "is_closed" in str(qs.query.where)


def test_value_min_filter_builds_query_without_hitting_db():
    filterset = OpportunityFilterSet(data={"value_min": "1000"}, queryset=Opportunity.objects.all())
    assert filterset.is_valid()
    qs = filterset.qs
    assert len(qs.query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_closed_filter_matches_real_rows(customer):
    open_opp = Opportunity.objects.create(customer=customer, title="Open")
    closed_opp = Opportunity.objects.create(customer=customer, title="Closed", is_closed=True)

    filterset = OpportunityFilterSet(data={"closed": "true"}, queryset=Opportunity.objects.all())
    assert list(filterset.qs) == [closed_opp]


@pytest.mark.django_db
def test_value_range_filter_matches_real_rows(customer):
    Opportunity.objects.create(customer=customer, title="Small", value="100.00")
    big = Opportunity.objects.create(customer=customer, title="Big", value="20000.00")

    filterset = OpportunityFilterSet(data={"value_min": "10000"}, queryset=Opportunity.objects.all())
    assert list(filterset.qs) == [big]
