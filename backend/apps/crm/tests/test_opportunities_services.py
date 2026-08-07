"""CP11: tests for the opportunity-pipeline functions in
apps/crm/services.py — the stage machine's actual business rules. Every
test requires a real database.
"""
import datetime

import pytest

from apps.crm.opportunities import Opportunity, OpportunityActivity, OpportunityNote
from apps.crm.services import (
    add_activity,
    add_note,
    advance_stage,
    create_opportunity,
    mark_lost,
    mark_won,
    reopen,
)

pytestmark = pytest.mark.django_db


# --------------------------------------------------------------------------
# create_opportunity()
# --------------------------------------------------------------------------


def test_create_opportunity_basic(customer):
    opp = create_opportunity(customer, "Big Deal", value="10000.00")
    assert opp.title == "Big Deal"
    assert opp.stage == Opportunity.Stage.NEW


def test_create_opportunity_sets_owner(customer, owner):
    opp = create_opportunity(customer, "Deal", owner=owner)
    assert opp.owner_id == owner.id


# --------------------------------------------------------------------------
# advance_stage() — "cannot move past WON/LOST unless reopened"
# --------------------------------------------------------------------------


def test_advance_stage_moves_between_open_stages(customer):
    opp = create_opportunity(customer, "Deal")
    advance_stage(opp, Opportunity.Stage.QUALIFIED)
    opp.refresh_from_db()
    assert opp.stage == Opportunity.Stage.QUALIFIED


def test_advance_stage_rejects_won_directly(customer):
    opp = create_opportunity(customer, "Deal")
    with pytest.raises(ValueError):
        advance_stage(opp, Opportunity.Stage.WON)


def test_advance_stage_rejects_lost_directly(customer):
    opp = create_opportunity(customer, "Deal")
    with pytest.raises(ValueError):
        advance_stage(opp, Opportunity.Stage.LOST)


def test_advance_stage_rejects_change_on_closed_opportunity(customer):
    opp = create_opportunity(customer, "Deal")
    mark_won(opp)

    with pytest.raises(ValueError):
        advance_stage(opp, Opportunity.Stage.QUALIFIED)


# --------------------------------------------------------------------------
# mark_won() — "WON automatically sets is_closed/is_won/actual_close_date"
# --------------------------------------------------------------------------


def test_mark_won_sets_all_three_fields_together(customer):
    opp = create_opportunity(customer, "Deal")

    mark_won(opp)

    assert opp.stage == Opportunity.Stage.WON
    assert opp.is_closed is True
    assert opp.is_won is True
    assert opp.actual_close_date == datetime.date.today()


def test_mark_won_persists(customer):
    opp = create_opportunity(customer, "Deal")
    mark_won(opp)
    opp.refresh_from_db()
    assert opp.is_closed is True
    assert opp.is_won is True


def test_mark_won_accepts_explicit_close_date(customer):
    opp = create_opportunity(customer, "Deal")
    custom_date = datetime.date(2026, 1, 1)

    mark_won(opp, actual_close_date=custom_date)

    assert opp.actual_close_date == custom_date


def test_mark_won_rejects_already_closed_opportunity(customer):
    opp = create_opportunity(customer, "Deal")
    mark_won(opp)

    with pytest.raises(ValueError):
        mark_won(opp)


# --------------------------------------------------------------------------
# mark_lost() — "LOST automatically sets is_closed=True, is_won=False"
# --------------------------------------------------------------------------


def test_mark_lost_sets_fields_together(customer):
    opp = create_opportunity(customer, "Deal")

    mark_lost(opp)

    assert opp.stage == Opportunity.Stage.LOST
    assert opp.is_closed is True
    assert opp.is_won is False
    assert opp.actual_close_date == datetime.date.today()


def test_mark_lost_rejects_already_closed_opportunity(customer):
    opp = create_opportunity(customer, "Deal")
    mark_lost(opp)

    with pytest.raises(ValueError):
        mark_lost(opp)


def test_mark_lost_on_a_won_opportunity_is_rejected(customer):
    opp = create_opportunity(customer, "Deal")
    mark_won(opp)

    with pytest.raises(ValueError):
        mark_lost(opp)


# --------------------------------------------------------------------------
# reopen() — "reopen() clears closing fields"
# --------------------------------------------------------------------------


def test_reopen_clears_closing_fields(customer):
    opp = create_opportunity(customer, "Deal")
    mark_won(opp)

    reopen(opp)

    assert opp.is_closed is False
    assert opp.is_won is False
    assert opp.actual_close_date is None
    assert opp.stage == Opportunity.Stage.NEW


def test_reopen_a_lost_opportunity(customer):
    opp = create_opportunity(customer, "Deal")
    mark_lost(opp)

    reopen(opp)

    assert opp.is_closed is False
    assert opp.stage == Opportunity.Stage.NEW


def test_reopen_rejects_an_already_open_opportunity(customer):
    opp = create_opportunity(customer, "Deal")

    with pytest.raises(ValueError):
        reopen(opp)


def test_reopen_accepts_custom_stage(customer):
    opp = create_opportunity(customer, "Deal")
    mark_won(opp)

    reopen(opp, stage=Opportunity.Stage.NEGOTIATION)

    assert opp.stage == Opportunity.Stage.NEGOTIATION


def test_reopen_rejects_won_or_lost_as_target_stage(customer):
    opp = create_opportunity(customer, "Deal")
    mark_won(opp)

    with pytest.raises(ValueError):
        reopen(opp, stage=Opportunity.Stage.WON)


def test_full_won_then_reopen_then_advance_cycle(customer):
    opp = create_opportunity(customer, "Deal")
    mark_won(opp)
    reopen(opp)
    advance_stage(opp, Opportunity.Stage.QUALIFIED)

    opp.refresh_from_db()
    assert opp.stage == Opportunity.Stage.QUALIFIED
    assert opp.is_closed is False


# --------------------------------------------------------------------------
# add_note() / add_activity()
# --------------------------------------------------------------------------


def test_add_note_creates_and_stamps_author(opportunity, owner):
    note = add_note(opportunity, "Great call today", created_by=owner)
    assert note.content == "Great call today"
    assert note.created_by_id == owner.id


def test_add_note_without_author_leaves_created_by_null(opportunity):
    note = add_note(opportunity, "Anonymous note")
    assert note.created_by_id is None


def test_add_activity_creates_and_stamps_author(opportunity, owner):
    activity = add_activity(opportunity, OpportunityActivity.ActivityType.CALL, "Intro call", created_by=owner)
    assert activity.subject == "Intro call"
    assert activity.activity_type == OpportunityActivity.ActivityType.CALL
    assert activity.created_by_id == owner.id


def test_add_activity_defaults_occurred_at_to_now(opportunity):
    activity = add_activity(opportunity, OpportunityActivity.ActivityType.EMAIL, "Follow-up")
    assert activity.occurred_at is not None
