"""CP14: tests for apps/activities/services.py."""
from datetime import date, datetime, timedelta

import pytest
from django.utils import timezone

from apps.activities.models import Event, Task
from apps.activities.services import (
    cancel_task,
    complete_task,
    create_event,
    create_reminder,
    create_task,
    generate_occurrences,
    get_timeline,
    log_activity,
    managed_user_ids,
    mark_reminder_sent,
    reassign_task,
    scope_queryset_for_user,
)

# --------------------------------------------------------------------------
# No database required — pure date-math
# --------------------------------------------------------------------------


def test_generate_occurrences_none_frequency_returns_single_occurrence():
    event = Event(start_at=timezone.make_aware(datetime(2026, 3, 1, 9, 0)))
    assert generate_occurrences(event) == [event.start_at]


def test_generate_occurrences_daily():
    event = Event(
        start_at=timezone.make_aware(datetime(2026, 3, 1, 9, 0)),
        recurrence_frequency=Event.RecurrenceFrequency.DAILY,
    )
    occurrences = generate_occurrences(event, limit=3)
    assert [dt.day for dt in occurrences] == [1, 2, 3]


def test_generate_occurrences_weekly():
    event = Event(
        start_at=timezone.make_aware(datetime(2026, 3, 1, 9, 0)),
        recurrence_frequency=Event.RecurrenceFrequency.WEEKLY,
    )
    occurrences = generate_occurrences(event, limit=2)
    assert (occurrences[1] - occurrences[0]).days == 7


def test_generate_occurrences_monthly_clamps_short_months():
    event = Event(
        start_at=timezone.make_aware(datetime(2026, 1, 31, 9, 0)),
        recurrence_frequency=Event.RecurrenceFrequency.MONTHLY,
    )
    occurrences = generate_occurrences(event, limit=2)
    assert occurrences[1].month == 2
    assert occurrences[1].day == 28  # 2026 is not a leap year


def test_generate_occurrences_yearly():
    event = Event(
        start_at=timezone.make_aware(datetime(2026, 3, 1, 9, 0)),
        recurrence_frequency=Event.RecurrenceFrequency.YEARLY,
    )
    occurrences = generate_occurrences(event, limit=2)
    assert occurrences[1].year == 2027


def test_generate_occurrences_stops_at_recurrence_end_date():
    event = Event(
        start_at=timezone.make_aware(datetime(2026, 3, 1, 9, 0)),
        recurrence_frequency=Event.RecurrenceFrequency.DAILY,
        recurrence_end_date=date(2026, 3, 2),
    )
    occurrences = generate_occurrences(event, limit=100)
    assert len(occurrences) == 2


def test_managed_user_ids_and_scope_queryset_for_user_are_reexported_from_crm():
    from apps.crm import services as crm_services

    assert managed_user_ids is crm_services.managed_user_ids
    assert scope_queryset_for_user is crm_services.scope_queryset_for_user


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_task_basic(employee):
    task = create_task("Draft proposal", owner=employee)
    assert task.owner_id == employee.id
    assert task.status == Task.Status.PENDING


@pytest.mark.django_db
def test_create_task_attaches_related_object(customer):
    from django.contrib.contenttypes.models import ContentType

    task = create_task("Renew", related_object=customer)
    assert task.content_type == ContentType.objects.get_for_model(customer)
    assert task.object_id == customer.pk


@pytest.mark.django_db
def test_reassign_task_changes_assignee(task, other_employee):
    reassign_task(task, other_employee)
    task.refresh_from_db()
    assert task.assigned_to_id == other_employee.id


@pytest.mark.django_db
def test_complete_task_sets_status_and_completed_at(task):
    complete_task(task)
    task.refresh_from_db()
    assert task.status == Task.Status.COMPLETED
    assert task.completed_at is not None


@pytest.mark.django_db
def test_complete_task_rejects_already_completed(task):
    complete_task(task)
    with pytest.raises(ValueError):
        complete_task(task)


@pytest.mark.django_db
def test_cancel_task_sets_status(task):
    cancel_task(task)
    task.refresh_from_db()
    assert task.status == Task.Status.CANCELLED


@pytest.mark.django_db
def test_cancel_task_rejects_already_cancelled(task):
    cancel_task(task)
    with pytest.raises(ValueError):
        cancel_task(task)


@pytest.mark.django_db
def test_create_event_basic(employee):
    event = create_event("Kickoff", timezone.now(), owner=employee)
    assert event.owner_id == employee.id


@pytest.mark.django_db
def test_log_activity_creates_entry_against_entity(customer, employee):
    log = log_activity(customer, "CALL", "Discussed renewal", actor=employee)
    assert log.description == "Discussed renewal"
    assert log.related_object == customer


@pytest.mark.django_db
def test_create_reminder_with_task(task):
    reminder = create_reminder(task=task, remind_at=timezone.now())
    assert reminder.task_id == task.id


@pytest.mark.django_db
def test_create_reminder_with_event(event):
    reminder = create_reminder(event=event, remind_at=timezone.now())
    assert reminder.event_id == event.id


@pytest.mark.django_db
def test_create_reminder_rejects_both(task, event):
    with pytest.raises(ValueError):
        create_reminder(task=task, event=event, remind_at=timezone.now())


@pytest.mark.django_db
def test_create_reminder_rejects_neither():
    with pytest.raises(ValueError):
        create_reminder(remind_at=timezone.now())


@pytest.mark.django_db
def test_mark_reminder_sent_is_idempotent(task):
    reminder = create_reminder(task=task, remind_at=timezone.now())
    mark_reminder_sent(reminder)
    mark_reminder_sent(reminder)  # calling twice must not raise
    reminder.refresh_from_db()
    assert reminder.is_sent is True


@pytest.mark.django_db
def test_get_timeline_merges_and_orders_by_recency(customer, employee):
    from apps.activities.models import Task as TaskModel

    old_log = log_activity(customer, "NOTE", "Old note", occurred_at=timezone.now() - timedelta(days=5))
    new_task = create_task("Recent task", owner=employee, related_object=customer, due_date=timezone.now())

    timeline = get_timeline(customer)

    kinds = [entry["kind"] for entry in timeline]
    assert kinds[0] == "task"  # more recent due_date sorts first
    assert "activity_log" in kinds
    assert timeline[0]["object"] == new_task
    assert timeline[-1]["object"] == old_log


@pytest.mark.django_db
def test_get_timeline_scoped_to_user_excludes_unowned_items(customer, employee, other_employee):
    create_task("Mine", owner=employee, related_object=customer)
    create_task("Not mine", owner=other_employee, related_object=customer)

    timeline = get_timeline(customer, user=employee)

    assert len(timeline) == 1
    assert timeline[0]["object"].owner_id == employee.id
