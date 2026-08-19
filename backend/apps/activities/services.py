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


# --------------------------------------------------------------------------
# Staff-management pass: the "Recent Activities" feed
# --------------------------------------------------------------------------

#: Every event kind the feed can emit. Stable machine names — a frontend
#: renders an icon/label per kind and never parses the human text.
RECENT_ACTIVITY_KINDS = (
    "LEAD_CONVERTED",
    "LEAD_ASSIGNED",
    "CUSTOMER_CREATED",
    "PAYMENT_RECEIVED",
    "PAYMENT_OVERDUE",
    "USER_CREATED",
    "FOLLOW_UP_SCHEDULED",
    "INTERACTION_LOGGED",
    "REMINDER_GENERATED",
    "CHECKED_IN",
    "CHECKED_OUT",
)

#: Default window and page size — a "recent activity" panel, not an archive.
RECENT_ACTIVITY_DEFAULT_DAYS = 7
RECENT_ACTIVITY_DEFAULT_LIMIT = 25


def get_recent_activity(user, *, limit=RECENT_ACTIVITY_DEFAULT_LIMIT, days=RECENT_ACTIVITY_DEFAULT_DAYS, now=None):
    """Real, role-scoped CRM events — never static placeholder text.

    Read-only aggregation over models that already record these events
    (``Lead``, ``Customer``, ``PaymentTransaction``/``Invoice``, ``Task``,
    ``Reminder``, ``CommunicationLog``, ``AttendanceSession``, ``User``).
    Deliberately NOT a new "activity feed" table: every entry here is a
    projection of a row that already exists, and a duplicate write-path
    would immediately be able to disagree with the ledger it mirrors.

    Scoping reuses ``scope_queryset_for_user()`` on every source queryset,
    so the three-tier rule is identical to every list endpoint:

    - Super Admin: org-wide (plus the org-wide-only kinds ``USER_CREATED``
      and ``PAYMENT_OVERDUE``, which are administrative by nature).
    - Manager: their own + their team's records only.
    - Employee: their own records only.

    Returns a list of dicts sorted most-recent-first::

        {"kind": "LEAD_CONVERTED", "timestamp": <datetime>,
         "title": str, "description": str,
         "entity_type": "lead"|"customer"|..., "entity_id": int|None,
         "actor_id": int|None, "actor_name": str}
    """
    from django.utils import timezone as dj_timezone

    from apps.accounts.models import User as UserModel
    from apps.accounts.permissions import is_super_admin
    from apps.attendance.models import AttendanceSession
    from apps.communications.models import CommunicationLog
    from apps.crm.models import Customer, Lead
    from apps.sales.models import Invoice, PaymentTransaction

    now = now or dj_timezone.now()
    since = now - timedelta(days=days)
    entries = []

    def _name(person):
        if person is None:
            return "System"
        return person.full_name or person.email

    # Leads converted / assigned. `updated_at` is when the conversion or
    # (re)assignment was written — Lead has no separate event table.
    leads = scope_queryset_for_user(
        Lead.active_objects.filter(updated_at__gte=since).select_related("owner", "converted_customer"),
        user,
        owner_field="owner",
    )
    for lead in leads[: limit * 2]:
        if lead.converted_customer_id:
            entries.append(
                {
                    "kind": "LEAD_CONVERTED",
                    "timestamp": lead.updated_at,
                    "title": f"Lead converted: {lead.company_name}",
                    "description": f"{lead.company_name} became a customer.",
                    "entity_type": "lead",
                    "entity_id": lead.id,
                    "actor_id": lead.owner_id,
                    "actor_name": _name(lead.owner),
                }
            )
        elif lead.owner_id:
            entries.append(
                {
                    "kind": "LEAD_ASSIGNED",
                    "timestamp": lead.updated_at,
                    "title": f"Lead assigned: {lead.company_name}",
                    "description": f"Assigned to {_name(lead.owner)}.",
                    "entity_type": "lead",
                    "entity_id": lead.id,
                    "actor_id": lead.owner_id,
                    "actor_name": _name(lead.owner),
                }
            )

    customers = scope_queryset_for_user(
        Customer.objects.filter(is_deleted=False, created_at__gte=since).select_related("owner"),
        user,
        owner_field="owner",
    )
    for customer in customers[:limit]:
        entries.append(
            {
                "kind": "CUSTOMER_CREATED",
                "timestamp": customer.created_at,
                "title": f"New customer: {customer.name}",
                "description": f"Owned by {_name(customer.owner)}.",
                "entity_type": "customer",
                "entity_id": customer.id,
                "actor_id": customer.owner_id,
                "actor_name": _name(customer.owner),
            }
        )

    payments = scope_queryset_for_user(
        PaymentTransaction.active_objects.filter(paid_at__gte=since).select_related("invoice", "invoice__owner"),
        user,
        owner_field="invoice__owner",
    )
    for payment in payments[:limit]:
        entries.append(
            {
                "kind": "PAYMENT_RECEIVED",
                "timestamp": payment.paid_at,
                "title": f"Payment received: {payment.amount}",
                "description": f"Invoice {payment.invoice.invoice_number}.",
                "entity_type": "invoice",
                "entity_id": payment.invoice_id,
                "actor_id": payment.invoice.owner_id,
                "actor_name": _name(payment.invoice.owner),
            }
        )

    overdue = scope_queryset_for_user(
        Invoice.active_objects.overdue().select_related("owner"), user, owner_field="owner"
    )
    for invoice in overdue.order_by("due_date")[:limit]:
        entries.append(
            {
                "kind": "PAYMENT_OVERDUE",
                "timestamp": now,
                "title": f"Invoice overdue: {invoice.invoice_number}",
                "description": f"Due {invoice.due_date}.",
                "entity_type": "invoice",
                "entity_id": invoice.id,
                "actor_id": invoice.owner_id,
                "actor_name": _name(invoice.owner),
            }
        )

    follow_ups = scope_queryset_for_user(
        Task.active_objects.filter(created_at__gte=since).select_related("owner", "assigned_to"),
        user,
        owner_field="owner",
    )
    for task in follow_ups[:limit]:
        entries.append(
            {
                "kind": "FOLLOW_UP_SCHEDULED",
                "timestamp": task.created_at,
                "title": f"Follow-up scheduled: {task.title}",
                "description": f"Due {task.due_date}." if task.due_date else "No due date set.",
                "entity_type": "task",
                "entity_id": task.id,
                "actor_id": task.owner_id,
                "actor_name": _name(task.owner),
            }
        )

    interactions = scope_queryset_for_user(
        CommunicationLog.active_objects.filter(occurred_at__gte=since).select_related("actor"),
        user,
        owner_field="actor",
    )
    for log in interactions[:limit]:
        entries.append(
            {
                "kind": "INTERACTION_LOGGED",
                "timestamp": log.occurred_at,
                "title": f"{log.channel.title()} interaction",
                "description": log.summary,
                "entity_type": "communication_log",
                "entity_id": log.id,
                "actor_id": log.actor_id,
                "actor_name": _name(log.actor),
            }
        )

    reminders = Reminder.active_objects.filter(created_at__gte=since).select_related("task__owner", "event__owner")
    reminders = _scope_reminders(reminders, user)
    for reminder in reminders[:limit]:
        owner = reminder.owner
        entries.append(
            {
                "kind": "REMINDER_GENERATED",
                "timestamp": reminder.created_at,
                "title": "Reminder generated",
                "description": reminder.message or f"Reminder at {reminder.remind_at}.",
                "entity_type": "reminder",
                "entity_id": reminder.id,
                "actor_id": getattr(owner, "id", None),
                "actor_name": _name(owner),
            }
        )

    sessions = scope_queryset_for_user(
        AttendanceSession.active_objects.filter(login_at__gte=since).select_related("employee"),
        user,
        owner_field="employee",
    )
    for session in sessions[:limit]:
        entries.append(
            {
                "kind": "CHECKED_IN",
                "timestamp": session.login_at,
                "title": f"{_name(session.employee)} checked in",
                "description": "",
                "entity_type": "attendance_session",
                "entity_id": session.id,
                "actor_id": session.employee_id,
                "actor_name": _name(session.employee),
            }
        )
        if session.logout_at is not None:
            entries.append(
                {
                    "kind": "CHECKED_OUT",
                    "timestamp": session.logout_at,
                    "title": f"{_name(session.employee)} checked out",
                    "description": "",
                    "entity_type": "attendance_session",
                    "entity_id": session.id,
                    "actor_id": session.employee_id,
                    "actor_name": _name(session.employee),
                }
            )

    # Staff creation is an org-wide administrative event: Super Admin only.
    if is_super_admin(user):
        for account in UserModel.objects.filter(date_joined__gte=since).order_by("-date_joined")[:limit]:
            entries.append(
                {
                    "kind": "USER_CREATED",
                    "timestamp": account.date_joined,
                    "title": f"{account.role.replace('_', ' ').title()} created",
                    "description": _name(account),
                    "entity_type": "user",
                    "entity_id": account.id,
                    "actor_id": account.id,
                    "actor_name": _name(account),
                }
            )

    entries.sort(key=lambda entry: entry["timestamp"], reverse=True)
    return entries[:limit]


def _scope_reminders(queryset, user):
    """`Reminder` has no owner column of its own — ownership is whichever
    of ``task``/``event`` it belongs to (see ``models.py``), the same shape
    ``ReminderViewSet.get_queryset()`` already handles with a Q expression.
    Mirrors that rule rather than inventing a second one.
    """
    from django.db.models import Q as DjangoQ

    from apps.accounts.permissions import is_super_admin, user_has_role_at_least
    from apps.accounts.models import User as UserModel

    if user is None or not getattr(user, "is_authenticated", False):
        return queryset.none()
    if is_super_admin(user):
        return queryset
    if user_has_role_at_least(user, UserModel.Role.MANAGER):
        ids = managed_user_ids(user)
        return queryset.filter(DjangoQ(task__owner_id__in=ids) | DjangoQ(event__owner_id__in=ids))
    return queryset.filter(DjangoQ(task__owner=user) | DjangoQ(event__owner=user))


__all__ = [
    "managed_user_ids",
    "scope_queryset_for_user",
    "RECENT_ACTIVITY_KINDS",
    "RECENT_ACTIVITY_DEFAULT_DAYS",
    "RECENT_ACTIVITY_DEFAULT_LIMIT",
    "get_recent_activity",
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
