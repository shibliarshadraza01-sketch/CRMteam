"""CP14: reusable service functions for the activity layer.

Following the CP9/CP10/CP11 pattern: narrow, single-purpose, independently
testable functions for operations with real behavior beyond a single ORM
call. Plain single-field updates that need no extra rule are not wrapped
here.

Ownership scoping (``managed_user_ids()``/``scope_queryset_for_user()``) is
NOT reimplemented — this module imports and reuses CP10's originals from
``apps.crm.services`` directly, exactly as CP14's rules require ("Use CP6
permissions", "Do not duplicate logic"). The "Employee owns their own
records; Manager sees their team's; Super Admin sees everything" rule stays
defined in exactly one place project-wide.
"""
from datetime import timedelta
from itertools import chain

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.crm.services import managed_user_ids, scope_queryset_for_user  # noqa: F401 (re-exported)

from .models import ActivityLog, Event, Reminder, Task

# --------------------------------------------------------------------------
# Task
# --------------------------------------------------------------------------


def create_task(title, *, owner=None, assigned_to=None, related_object=None, **extra_fields):
    """Create a `Task`, optionally attached to a CRM entity via
    `related_object` (any `Customer`/`Lead`/`Opportunity`/`Quote`/`Invoice`
    instance — resolved into `content_type`/`object_id` here so callers
    never have to touch the contenttypes framework directly).
    """
    if related_object is not None:
        extra_fields["content_type"] = ContentType.objects.get_for_model(related_object)
        extra_fields["object_id"] = related_object.pk
    return Task.objects.create(title=title, owner=owner, assigned_to=assigned_to, **extra_fields)


def reassign_task(task, user):
    """Reassign `task` to a different user (or unassign, with ``user=None``).
    A thin wrapper — kept for architectural symmetry with CP9/CP10's
    ``assign_owner()`` and as the single seam a future "notify the new
    assignee" rule would be added to.
    """
    task.assigned_to = user
    task.save(update_fields=["assigned_to", "updated_at"])
    return task


def complete_task(task):
    """Mark `task` completed — sets ``status=COMPLETED`` and stamps
    ``completed_at`` together, so a task can never end up "completed" with
    no completion time recorded. Raises ``ValueError`` if the task is
    already completed or cancelled — same "already closed" guard shape as
    CP11's ``mark_won()``/``mark_lost()``.
    """
    if task.status in (Task.Status.COMPLETED, Task.Status.CANCELLED):
        raise ValueError("This task is already completed or cancelled.")

    task.status = Task.Status.COMPLETED
    task.completed_at = timezone.now()
    task.save(update_fields=["status", "completed_at", "updated_at"])
    return task


def cancel_task(task):
    """Mark `task` cancelled. Raises ``ValueError`` if already completed or
    cancelled — same guard as ``complete_task()``.
    """
    if task.status in (Task.Status.COMPLETED, Task.Status.CANCELLED):
        raise ValueError("This task is already completed or cancelled.")

    task.status = Task.Status.CANCELLED
    task.save(update_fields=["status", "updated_at"])
    return task


# --------------------------------------------------------------------------
# Event
# --------------------------------------------------------------------------


def create_event(title, start_at, *, owner=None, related_object=None, **extra_fields):
    """Create an `Event`, optionally attached to a CRM entity — same
    `related_object` convention as ``create_task()``.
    """
    if related_object is not None:
        extra_fields["content_type"] = ContentType.objects.get_for_model(related_object)
        extra_fields["object_id"] = related_object.pk
    return Event.objects.create(title=title, start_at=start_at, owner=owner, **extra_fields)


def generate_occurrences(event, *, limit=52):
    """Compute the recurrence occurrence datetimes for `event`.

    "Basic recurrence only" (CP14's own wording): this is a pure date-math
    calculation — DAILY/WEEKLY/MONTHLY/YEARLY stepping from ``start_at`` up
    to ``recurrence_end_date`` (or ``limit`` occurrences, whichever comes
    first) — NOT a full RFC 5545 RRULE engine (no BYDAY/BYMONTH/exceptions/
    until-vs-count combinations). Returns a plain list of `datetime`s; it
    deliberately does NOT persist additional `Event` rows — a single `Event`
    represents the recurring series, and this function answers "when does it
    next occur", not "materialize every future occurrence as its own row".
    """
    if event.recurrence_frequency == Event.RecurrenceFrequency.NONE:
        return [event.start_at]

    step_by = {
        Event.RecurrenceFrequency.DAILY: lambda dt, n: dt + timedelta(days=n),
        Event.RecurrenceFrequency.WEEKLY: lambda dt, n: dt + timedelta(weeks=n),
        Event.RecurrenceFrequency.MONTHLY: lambda dt, n: _add_months(dt, n),
        Event.RecurrenceFrequency.YEARLY: lambda dt, n: _add_months(dt, n * 12),
    }[event.recurrence_frequency]

    occurrences = []
    for n in range(limit):
        occurrence = step_by(event.start_at, n)
        if event.recurrence_end_date and occurrence.date() > event.recurrence_end_date:
            break
        occurrences.append(occurrence)
    return occurrences


def _add_months(dt, months):
    """Add ``months`` calendar months to ``dt``, clamping the day-of-month
    to the target month's actual length (e.g. Jan 31 + 1 month -> Feb 28/29,
    not an invalid Feb 31). Kept private — a small date-math helper for
    ``generate_occurrences()``, not a general-purpose utility.
    """
    month_index = dt.month - 1 + months
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    last_day_of_month = (
        (dt.replace(year=year, month=month % 12 + 1, day=1) if month != 12 else dt.replace(year=year + 1, month=1, day=1))
        - timedelta(days=1)
    ).day
    day = min(dt.day, last_day_of_month)
    return dt.replace(year=year, month=month, day=day)


# --------------------------------------------------------------------------
# ActivityLog
# --------------------------------------------------------------------------


def log_activity(entity, activity_type, description, *, actor=None, occurred_at=None):
    """Log an `ActivityLog` entry against any CRM `entity` — the generic
    counterpart to CP11's ``add_activity()`` (Opportunity-only).
    """
    return ActivityLog.objects.create(
        content_type=ContentType.objects.get_for_model(entity),
        object_id=entity.pk,
        activity_type=activity_type,
        description=description,
        actor=actor,
        occurred_at=occurred_at or timezone.now(),
    )


# --------------------------------------------------------------------------
# Reminder
# --------------------------------------------------------------------------


def create_reminder(*, task=None, event=None, remind_at, message=""):
    """Create a `Reminder` for exactly one of `task`/`event`.

    Raises ``ValueError`` up front (mirroring the DB constraint — see
    CP13's ``add_pricebook_entry()`` for the same "validation is UX, the
    constraint is the real guarantee" layering) if both or neither is
    supplied.
    """
    if (task is None) == (event is None):
        raise ValueError("Exactly one of task or event must be supplied.")
    return Reminder.objects.create(task=task, event=event, remind_at=remind_at, message=message)


def mark_reminder_sent(reminder):
    """Mark `reminder` as sent. Idempotent on purpose — unlike CP12's
    ``mark_invoice_paid()``, re-marking an already-sent reminder is not a
    caller error worth guarding against (no invariant is broken by sending
    the same reminder notification's "sent" flag twice).
    """
    reminder.is_sent = True
    reminder.save(update_fields=["is_sent", "updated_at"])
    return reminder


# --------------------------------------------------------------------------
# Activity timeline retrieval
# --------------------------------------------------------------------------


def get_timeline(entity, *, user=None):
    """Return every `Task`/`Event`/`ActivityLog` attached to `entity`
    (a `Customer`/`Lead`/`Opportunity`/`Quote`/`Invoice` instance), merged
    into one chronologically-ordered (most recent first) list of dicts.

    `Task`/`Event`/`ActivityLog` have no common queryset shape to `union()`
    across (different fields, different "when" columns), so this fetches
    each active queryset for `entity` separately and merges them in Python —
    fine at the scale a single entity's timeline is ever expected to reach.
    Each entry is tagged with ``"kind"`` so a caller/serializer can tell
    which model it came from.

    When ``user`` is supplied, each queryset is scoped through CP10's
    ``scope_queryset_for_user()`` first (own items only for an Employee,
    team's items for a Manager, everything for a Super Admin) — the same
    ownership rule this app's viewsets already apply, reused rather than
    reinvented for the timeline endpoint. ``user=None`` (the default) skips
    scoping entirely, for internal/admin callers that already know they're
    allowed to see everything.
    """
    content_type = ContentType.objects.get_for_model(entity)

    tasks = Task.active_objects.filter(content_type=content_type, object_id=entity.pk)
    events = Event.active_objects.filter(content_type=content_type, object_id=entity.pk)
    logs = ActivityLog.active_objects.filter(content_type=content_type, object_id=entity.pk)

    if user is not None:
        tasks = scope_queryset_for_user(tasks, user, owner_field="owner")
        events = scope_queryset_for_user(events, user, owner_field="owner")
        logs = scope_queryset_for_user(logs, user, owner_field="actor")

    entries = chain(
        ({"kind": "task", "timestamp": t.due_date or t.created_at, "object": t} for t in tasks),
        ({"kind": "event", "timestamp": e.start_at, "object": e} for e in events),
        ({"kind": "activity_log", "timestamp": l.occurred_at, "object": l} for l in logs),
    )
    return sorted(entries, key=lambda entry: entry["timestamp"], reverse=True)


__all__ = [
    "managed_user_ids",
    "scope_queryset_for_user",
    "create_task",
    "reassign_task",
    "complete_task",
    "cancel_task",
    "create_event",
    "generate_occurrences",
    "log_activity",
    "create_reminder",
    "mark_reminder_sent",
    "get_timeline",
]
