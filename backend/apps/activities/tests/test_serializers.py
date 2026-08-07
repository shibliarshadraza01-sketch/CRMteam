"""CP14: tests for apps/activities/serializers.py."""
import pytest
from rest_framework import serializers

from apps.activities.serializers import (
    ActivityLogSerializer,
    EventSerializer,
    ReminderDetailSerializer,
    ReminderSerializer,
    TaskSerializer,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_task_serializer_fields():
    fields = TaskSerializer().fields
    assert {
        "id", "title", "description", "owner", "assigned_to", "priority", "status",
        "due_date", "completed_at", "content_type", "object_id", "related_object",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_task_serializer_related_object_is_read_only():
    assert TaskSerializer().fields["related_object"].read_only is True


def test_event_serializer_fields_include_recurrence_and_is_recurring():
    fields = EventSerializer().fields
    assert "recurrence_frequency" in fields
    assert "recurrence_end_date" in fields
    assert fields["is_recurring"].read_only is True


def test_activitylog_serializer_fields():
    fields = ActivityLogSerializer().fields
    assert {
        "id", "actor", "activity_type", "description", "occurred_at",
        "content_type", "object_id", "related_object",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_related_object_summary_returns_none_without_content_type():
    class Dummy:
        content_type_id = None
        object_id = None

    serializer = TaskSerializer()
    assert serializer.get_related_object(Dummy()) is None


def test_reminder_serializer_rejects_both_task_and_event():
    serializer = ReminderSerializer()
    with pytest.raises(serializers.ValidationError):
        serializer.validate({"task": object(), "event": object()})


def test_reminder_serializer_rejects_neither():
    serializer = ReminderSerializer()
    with pytest.raises(serializers.ValidationError):
        serializer.validate({"task": None, "event": None})


def test_reminder_serializer_accepts_task_only():
    serializer = ReminderSerializer()
    attrs = {"task": object(), "event": None}
    assert serializer.validate(attrs) == attrs


def test_reminder_detail_serializer_is_entirely_read_only():
    for name, field in ReminderDetailSerializer().fields.items():
        assert field.read_only is True


# --------------------------------------------------------------------------
# Requires database — full serializer validation (FK fields query the DB)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_task_serializer_full_validation_accepts_minimal_payload(employee):
    serializer = TaskSerializer(data={"title": "Follow up", "owner": employee.pk})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_reminder_serializer_full_validation_with_task(task):
    from django.utils import timezone

    serializer = ReminderSerializer(data={"task": task.pk, "remind_at": timezone.now()})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_task_serializer_related_object_output(customer):
    from apps.activities.services import create_task

    task = create_task("Renew", related_object=customer)
    data = TaskSerializer(task).data

    assert data["related_object"]["label"] == str(customer)
    assert data["related_object"]["type"] == "crm.customer"
