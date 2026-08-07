"""CP11: tests for Opportunity.objects / OpportunityQuerySet."""
import datetime

import pytest

from apps.crm.opportunities import Opportunity

# --------------------------------------------------------------------------
# No database required — queryset structure
# --------------------------------------------------------------------------


def test_opportunity_manager_has_expected_helpers():
    for helper in ("by_stage", "open", "closed", "won", "lost", "high_value", "expected_this_month"):
        assert hasattr(Opportunity.objects, helper)


def test_by_stage_filters_without_hitting_db():
    queryset = Opportunity.objects.by_stage(Opportunity.Stage.PROPOSAL)
    assert len(queryset.query.where) > 0


def test_open_and_closed_are_opposite_filters():
    open_sql = str(Opportunity.objects.open().query.where)
    closed_sql = str(Opportunity.objects.closed().query.where)
    assert "is_closed" in open_sql
    assert "is_closed" in closed_sql
    assert open_sql != closed_sql


def test_won_filters_on_is_won():
    queryset = Opportunity.objects.won()
    assert "is_won" in str(queryset.query.where)


def test_lost_filters_on_both_is_closed_and_not_is_won():
    queryset = Opportunity.objects.lost()
    where_sql = str(queryset.query.where)
    assert "is_closed" in where_sql
    assert "is_won" in where_sql


def test_high_value_uses_default_threshold_without_hitting_db():
    queryset = Opportunity.objects.high_value()
    assert len(queryset.query.where) > 0


def test_expected_this_month_accepts_injectable_today_without_hitting_db():
    queryset = Opportunity.objects.expected_this_month(today=datetime.date(2026, 3, 15))
    assert "expected_close_date" in str(queryset.query.where)


def test_active_objects_does_not_filter_by_a_business_active_flag():
    # Unlike Customer (CP9), Opportunity has no separate is_active field —
    # active_objects means only "not soft-deleted".
    where_sql = str(Opportunity.active_objects.all().query.where)
    assert "is_deleted" in where_sql
    assert "is_active" not in where_sql


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_by_stage_returns_only_matching_rows(customer):
    Opportunity.objects.create(customer=customer, title="A", stage=Opportunity.Stage.PROPOSAL)
    Opportunity.objects.create(customer=customer, title="B", stage=Opportunity.Stage.NEGOTIATION)

    titles = set(Opportunity.objects.by_stage(Opportunity.Stage.PROPOSAL).values_list("title", flat=True))

    assert titles == {"A"}


@pytest.mark.django_db
def test_open_and_closed_return_correct_rows(customer):
    open_opp = Opportunity.objects.create(customer=customer, title="Open")
    closed_opp = Opportunity.objects.create(customer=customer, title="Closed", is_closed=True, is_won=True)

    assert list(Opportunity.objects.open()) == [open_opp]
    assert list(Opportunity.objects.closed()) == [closed_opp]


@pytest.mark.django_db
def test_won_and_lost_return_correct_rows(customer):
    won = Opportunity.objects.create(customer=customer, title="Won", is_closed=True, is_won=True)
    lost = Opportunity.objects.create(customer=customer, title="Lost", is_closed=True, is_won=False)
    Opportunity.objects.create(customer=customer, title="Open")  # neither

    assert list(Opportunity.objects.won()) == [won]
    assert list(Opportunity.objects.lost()) == [lost]


@pytest.mark.django_db
def test_high_value_uses_custom_threshold(customer):
    small = Opportunity.objects.create(customer=customer, title="Small", value="500.00")
    big = Opportunity.objects.create(customer=customer, title="Big", value="50000.00")

    default_threshold = set(Opportunity.objects.high_value().values_list("title", flat=True))
    custom_threshold = set(Opportunity.objects.high_value(threshold=100).values_list("title", flat=True))

    assert default_threshold == {"Big"}
    assert custom_threshold == {"Small", "Big"}


@pytest.mark.django_db
def test_expected_this_month_matches_only_current_month(customer):
    today = datetime.date(2026, 3, 15)
    this_month = Opportunity.objects.create(
        customer=customer, title="ThisMonth", expected_close_date=datetime.date(2026, 3, 1)
    )
    Opportunity.objects.create(customer=customer, title="NextMonth", expected_close_date=datetime.date(2026, 4, 1))
    Opportunity.objects.create(customer=customer, title="NoDate")

    result = Opportunity.objects.expected_this_month(today=today)

    assert list(result) == [this_month]


@pytest.mark.django_db
def test_expected_this_month_handles_december_year_rollover(customer):
    december_deal = Opportunity.objects.create(
        customer=customer, title="Dec", expected_close_date=datetime.date(2026, 12, 20)
    )
    Opportunity.objects.create(customer=customer, title="Jan", expected_close_date=datetime.date(2027, 1, 1))

    result = Opportunity.objects.expected_this_month(today=datetime.date(2026, 12, 5))

    assert list(result) == [december_deal]
