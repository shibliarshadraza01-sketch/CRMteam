"""CP11: tests for the Opportunity-related serializers in
apps/crm/serializers.py.
"""
import pytest
from rest_framework import serializers

from apps.crm.opportunities import Opportunity
from apps.crm.serializers import (
    OpportunityActivitySerializer,
    OpportunityDetailSerializer,
    OpportunityNoteSerializer,
    OpportunitySerializer,
    OpportunityStageTransitionSerializer,
)

# --------------------------------------------------------------------------
# No database required — field declarations
# --------------------------------------------------------------------------


def test_opportunity_serializer_fields():
    fields = OpportunitySerializer().fields
    assert {
        "id", "customer", "owner", "title", "stage", "value", "probability",
        "expected_close_date", "actual_close_date", "currency", "description",
        "is_closed", "is_won",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_opportunity_serializer_closing_fields_are_read_only():
    fields = OpportunitySerializer().fields
    for name in ("is_closed", "is_won", "actual_close_date"):
        assert fields[name].read_only is True


def test_opportunity_serializer_stage_is_writable():
    field = OpportunitySerializer().fields["stage"]
    assert field.read_only is False


def test_opportunity_serializer_validate_stage_rejects_won_directly():
    # validate_stage() is a plain field-level validator — exercised
    # directly, without going through the full serializer (whose
    # `customer` PrimaryKeyRelatedField would otherwise need a database to
    # resolve, unrelated to what this test is actually checking).
    serializer = OpportunitySerializer()
    with pytest.raises(serializers.ValidationError):
        serializer.validate_stage(Opportunity.Stage.WON)


def test_opportunity_serializer_validate_stage_rejects_lost_directly():
    serializer = OpportunitySerializer()
    with pytest.raises(serializers.ValidationError):
        serializer.validate_stage(Opportunity.Stage.LOST)


def test_opportunity_serializer_validate_stage_accepts_open_stage():
    serializer = OpportunitySerializer()
    assert serializer.validate_stage(Opportunity.Stage.QUALIFIED) == Opportunity.Stage.QUALIFIED


# --------------------------------------------------------------------------
# Requires database — full serializer validation (the `customer` PK field
# queries the database to confirm the referenced row exists)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_opportunity_serializer_rejects_won_stage_directly(customer):
    serializer = OpportunitySerializer(data={"customer": customer.pk, "title": "Deal", "stage": Opportunity.Stage.WON})
    assert serializer.is_valid() is False
    assert "stage" in serializer.errors


@pytest.mark.django_db
def test_opportunity_serializer_accepts_open_stage(customer):
    serializer = OpportunitySerializer(data={"customer": customer.pk, "title": "Deal", "stage": Opportunity.Stage.QUALIFIED})
    assert serializer.is_valid(), serializer.errors


def test_opportunity_detail_serializer_nests_owner_customer_name_notes_activities():
    fields = OpportunityDetailSerializer().fields
    assert isinstance(fields["owner"], serializers.Serializer)
    assert "customer_name" in fields
    assert isinstance(fields["notes"], serializers.ListSerializer)
    assert isinstance(fields["activities"], serializers.ListSerializer)


def test_opportunity_detail_serializer_is_entirely_read_only():
    for name, field in OpportunityDetailSerializer().fields.items():
        assert field.read_only is True, f"{name} should be read-only"


def test_opportunity_note_serializer_fields():
    fields = OpportunityNoteSerializer().fields
    assert {"id", "opportunity", "content"} <= set(fields.keys())


def test_opportunity_activity_serializer_fields():
    fields = OpportunityActivitySerializer().fields
    assert {"id", "opportunity", "activity_type", "subject", "notes", "occurred_at"} <= set(fields.keys())


def test_stage_transition_serializer_only_has_stage_field():
    fields = OpportunityStageTransitionSerializer().fields
    assert set(fields.keys()) == {"stage"}


def test_stage_transition_serializer_accepts_valid_stage():
    serializer = OpportunityStageTransitionSerializer(data={"stage": "QUALIFIED"})
    assert serializer.is_valid(), serializer.errors


def test_stage_transition_serializer_rejects_invalid_stage():
    serializer = OpportunityStageTransitionSerializer(data={"stage": "NOT_A_REAL_STAGE"})
    assert serializer.is_valid() is False


# --------------------------------------------------------------------------
# Requires database — serializing a real instance
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_opportunity_detail_serializer_output(opportunity, owner):
    from apps.crm.services import add_note

    add_note(opportunity, "hello", created_by=owner)

    data = OpportunityDetailSerializer(opportunity).data

    assert data["owner"]["email"] == owner.email
    assert data["customer_name"] == opportunity.customer.name
    assert len(data["notes"]) == 1
