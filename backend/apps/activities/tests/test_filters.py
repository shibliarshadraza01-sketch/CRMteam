"""CP14: tests for apps/activities/filters.py."""
import pytest

from apps.activities.filters import EventFilterSet, ReminderFilterSet, TaskFilterSet
from apps.activities.models import Task

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_task_filterset_declares_expected_fields():
    assert set(TaskFilterSet.Meta.fields) == {
        "status", "priority", "owner", "assigned_to", "content_type", "object_id",
    }
    assert "due_before" in TaskFilterSet.declared_filters
    assert "due_after" in TaskFilterSet.declared_filters


def test_event_filterset_declares_expected_fields():
    assert set(EventFilterSet.Meta.fields) == {"owner", "recurrence_frequency", "content_type", "object_id"}


def test_reminder_filterset_declares_expected_fields():
    assert set(ReminderFilterSet.Meta.fields) == {"task", "event", "is_sent"}


def test_due_range_filter_builds_query_without_hitting_db():
    filterset = TaskFilterSet(data={"due_before": "2026-12-31T00:00:00Z"}, queryset=Task.objects.all())
    assert filterset.is_valid()
    assert len(filterset.qs.query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_due_range_filter_matches_real_rows(employee):
    from datetime import timedelta

    from django.utils import timezone

    soon = Task.objects.create(title="Soon", owner=employee, due_date=timezone.now() + timedelta(days=1))
    Task.objects.create(title="Far", owner=employee, due_date=timezone.now() + timedelta(days=30))

    filterset = TaskFilterSet(
        data={"due_before": (timezone.now() + timedelta(days=5)).isoformat()}, queryset=Task.objects.all()
    )

    assert list(filterset.qs) == [soon]


@pytest.mark.django_db
def test_status_filter_matches_real_rows(employee):
    open_task = Task.objects.create(title="Open", owner=employee)
    Task.objects.create(title="Done", owner=employee, status=Task.Status.COMPLETED)

    filterset = TaskFilterSet(data={"status": Task.Status.PENDING}, queryset=Task.objects.all())

    assert list(filterset.qs) == [open_task]
