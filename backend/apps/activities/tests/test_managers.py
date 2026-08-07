"""CP14: tests for the querysets on apps/activities/models.py."""
import pytest

from apps.activities.models import ActivityLog, Event, Reminder, Task

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_task_open_excludes_completed_and_cancelled_without_hitting_db():
    where_sql = str(Task.objects.open().query.where)
    assert "status" in where_sql


def test_event_upcoming_filters_on_start_at_without_hitting_db():
    where_sql = str(Event.objects.upcoming().query.where)
    assert "start_at" in where_sql


def test_reminder_due_filters_on_remind_at_and_is_sent_without_hitting_db():
    where_sql = str(Reminder.objects.due().query.where)
    assert "remind_at" in where_sql
    assert "is_sent" in where_sql


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_task_open_excludes_completed_and_cancelled(employee):
    open_task = Task.objects.create(title="Open", owner=employee)
    Task.objects.create(title="Done", owner=employee, status=Task.Status.COMPLETED)
    Task.objects.create(title="Cancelled", owner=employee, status=Task.Status.CANCELLED)

    assert list(Task.objects.open()) == [open_task]


@pytest.mark.django_db
def test_task_for_entity_matches_real_rows(customer):
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(customer)
    matching = Task.objects.create(title="Match", content_type=content_type, object_id=customer.pk)
    Task.objects.create(title="No match")

    assert list(Task.objects.for_entity(customer)) == [matching]


@pytest.mark.django_db
def test_active_task_manager_excludes_deleted(employee):
    active = Task.objects.create(title="Active", owner=employee)
    deleted = Task.objects.create(title="Deleted", owner=employee)
    deleted.soft_delete()

    assert list(Task.active_objects.values_list("title", flat=True)) == ["Active"]


@pytest.mark.django_db
def test_reminder_due_matches_only_unsent_past_due(task):
    from datetime import timedelta

    from django.utils import timezone

    due = Reminder.objects.create(task=task, remind_at=timezone.now() - timedelta(hours=1))
    Reminder.objects.create(task=task, remind_at=timezone.now() + timedelta(hours=1))
    sent = Reminder.objects.create(task=task, remind_at=timezone.now() - timedelta(hours=2), is_sent=True)

    result = set(Reminder.objects.due().values_list("pk", flat=True))

    assert result == {due.pk}
    assert sent.pk not in result


@pytest.mark.django_db
def test_activitylog_for_entity_matches_real_rows(customer):
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(customer)
    matching = ActivityLog.objects.create(
        description="Called", content_type=content_type, object_id=customer.pk
    )
    ActivityLog.objects.create(description="Unrelated")

    assert list(ActivityLog.objects.for_entity(customer)) == [matching]
