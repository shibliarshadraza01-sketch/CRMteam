"""CP11: tests for apps/crm/opportunities.py's models.

Split, following the CP4-CP10 pattern, into DB-free tests (field/Meta
definitions, pure-Python properties on in-memory instances) and
DB-dependent tests (persistence, constraints, cascade behavior) — the
latter honestly blocked by the same missing-PostgreSQL issue as every
DB-backed test since CP2.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import models

from apps.crm.models import Customer
from apps.crm.opportunities import Opportunity, OpportunityActivity, OpportunityNote

User = get_user_model()


def _unsaved_user(role=User.Role.EMPLOYEE, email="user@example.com"):
    return User(email=email, role=role)


# --------------------------------------------------------------------------
# No database required — field/Meta definitions
# --------------------------------------------------------------------------


def test_opportunity_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in Opportunity._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_opportunity_fk_related_names():
    customer_field = Opportunity._meta.get_field("customer")
    owner_field = Opportunity._meta.get_field("owner")
    assert customer_field.remote_field.related_name == "opportunities"
    assert customer_field.remote_field.on_delete is models.CASCADE
    assert owner_field.remote_field.related_name == "owned_opportunities"
    assert owner_field.remote_field.on_delete is models.SET_NULL
    assert owner_field.null is True


def test_opportunity_stage_default_is_new():
    assert Opportunity._meta.get_field("stage").default == Opportunity.Stage.NEW


def test_opportunity_stage_choices_match_spec():
    values = {choice.value for choice in Opportunity.Stage}
    assert values == {"NEW", "QUALIFIED", "PROPOSAL", "NEGOTIATION", "WON", "LOST"}


def test_opportunity_value_is_decimal_not_float():
    field = Opportunity._meta.get_field("value")
    assert isinstance(field, models.DecimalField)
    assert field.max_digits == 14
    assert field.decimal_places == 2


def test_opportunity_probability_has_0_100_validators():
    field = Opportunity._meta.get_field("probability")
    validator_limits = {(type(v).__name__, v.limit_value) for v in field.validators}
    assert ("MinValueValidator", 0) in validator_limits
    assert ("MaxValueValidator", 100) in validator_limits


def test_opportunity_is_closed_and_is_won_default_false():
    assert Opportunity._meta.get_field("is_closed").default is False
    assert Opportunity._meta.get_field("is_won").default is False


def test_opportunity_currency_defaults_to_usd():
    assert Opportunity._meta.get_field("currency").default == "USD"


def test_opportunity_str_includes_title_and_customer_name():
    customer = Customer(name="Globex")
    opportunity = Opportunity(title="Big Deal", customer=customer)
    assert str(opportunity) == "Big Deal (Globex)"


def test_opportunity_manager_has_access_false_with_no_owner():
    customer = Customer(name="Globex")
    opportunity = Opportunity(title="Deal", customer=customer)
    manager = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    assert opportunity.manager_has_access(manager) is False


def test_opportunityactivity_fk_related_name():
    field = OpportunityActivity._meta.get_field("opportunity")
    assert field.remote_field.related_name == "activities"
    assert field.remote_field.on_delete is models.CASCADE


def test_opportunityactivity_type_choices():
    values = {choice.value for choice in OpportunityActivity.ActivityType}
    assert values == {"CALL", "EMAIL", "MEETING", "TASK", "OTHER"}


def test_opportunityactivity_str_includes_type_and_subject():
    activity = OpportunityActivity(activity_type=OpportunityActivity.ActivityType.CALL, subject="Intro call")
    assert "Call" in str(activity)
    assert "Intro call" in str(activity)


def test_opportunityactivity_owner_delegates_to_opportunity():
    owner = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    customer = Customer(name="Globex")
    opportunity = Opportunity(title="Deal", customer=customer, owner=owner)
    activity = OpportunityActivity(opportunity=opportunity, subject="Call")
    assert activity.owner is owner


def test_opportunitynote_fk_related_name():
    field = OpportunityNote._meta.get_field("opportunity")
    assert field.remote_field.related_name == "notes"
    assert field.remote_field.on_delete is models.CASCADE


def test_opportunitynote_str_truncates_long_content():
    note = OpportunityNote(content="x" * 100)
    assert str(note).endswith("…")
    assert len(str(note)) == 51  # 50 chars + ellipsis


def test_opportunitynote_str_does_not_truncate_short_content():
    note = OpportunityNote(content="short note")
    assert str(note) == "short note"


def test_opportunitynote_owner_delegates_to_opportunity():
    owner = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    customer = Customer(name="Globex")
    opportunity = Opportunity(title="Deal", customer=customer, owner=owner)
    note = OpportunityNote(opportunity=opportunity, content="hello")
    assert note.owner is owner


# --------------------------------------------------------------------------
# Requires database — persistence, cascades
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_opportunity_create_and_retrieve(customer, owner):
    opp = Opportunity.objects.create(customer=customer, title="Big Deal", owner=owner, value="5000.00")
    fetched = Opportunity.objects.get(pk=opp.pk)
    assert fetched.title == "Big Deal"
    assert fetched.stage == Opportunity.Stage.NEW


@pytest.mark.django_db
def test_deleting_customer_cascades_to_opportunities(customer):
    opp = Opportunity.objects.create(customer=customer, title="Deal")
    customer.delete()
    assert not Opportunity.objects.filter(pk=opp.pk).exists()


@pytest.mark.django_db
def test_deleting_owner_sets_null_not_cascade(customer, owner):
    opp = Opportunity.objects.create(customer=customer, title="Deal", owner=owner)
    owner.delete()
    opp.refresh_from_db()
    assert opp.owner_id is None


@pytest.mark.django_db
def test_deleting_opportunity_cascades_to_activities_and_notes(opportunity):
    activity = OpportunityActivity.objects.create(opportunity=opportunity, subject="Call")
    note = OpportunityNote.objects.create(opportunity=opportunity, content="hi")

    opportunity.delete()

    assert not OpportunityActivity.objects.filter(pk=activity.pk).exists()
    assert not OpportunityNote.objects.filter(pk=note.pk).exists()


@pytest.mark.django_db
def test_reverse_relationships_traverse_opportunity_to_children(opportunity):
    OpportunityActivity.objects.create(opportunity=opportunity, subject="Call")
    OpportunityNote.objects.create(opportunity=opportunity, content="hi")

    assert opportunity.activities.count() == 1
    assert opportunity.notes.count() == 1
    assert opportunity.customer.opportunities.count() == 1


@pytest.mark.django_db
def test_opportunity_manager_has_access_true_for_team_manager(organization, manager, employee, managed_team):
    customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs-opp", owner=employee)
    opp = Opportunity.objects.create(customer=customer, title="Deal", owner=employee)
    assert opp.manager_has_access(manager) is True


@pytest.mark.django_db
def test_opportunity_manager_has_access_false_for_unrelated_manager(organization, employee, django_user_model):
    unrelated = django_user_model.objects.create_user(
        email="unrelated-opp@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs-opp2", owner=employee)
    opp = Opportunity.objects.create(customer=customer, title="Deal", owner=employee)
    assert opp.manager_has_access(unrelated) is False
