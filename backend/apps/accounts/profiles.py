"""Staff-management pass: the Super Admin's (and a Manager's, in scope)
consolidated view of ONE staff member — "Employee Profile" and "Manager
Profile" in the spec.

Read-only aggregation over models that already exist (``Lead``,
``Customer``, ``Task``, ``Event``, ``ActivityLog``, ``CommunicationLog``,
``AttendanceSession``, ``Team``/``Membership``) — deliberately NOT a new
"profile" table, because every number here is derivable and a stored copy
would immediately start drifting from the ledgers it summarizes (the same
"derived, never hand-edited" rule ``apps.attendance.services`` already
follows).

Kept in its own module (alongside ``challenge.py``/``session_utils.py``,
this app's existing convention for focused non-view logic) rather than in
``services.py``, which is strictly session/user-lifecycle code and must
not grow cross-app CRM imports.

Access is decided by the CALLER (see ``apps/accounts/views.py``'s
``StaffProfileView``) using ``can_view_staff_profile()`` below, which is
built on the same ``managed_user_ids()`` boundary the rest of the project
uses — no new scoping concept is introduced here.
"""
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import is_super_admin, user_has_role_at_least


def can_view_staff_profile(requesting_user, target_user):
    """Who may read whose staff profile.

    - Super Admin: anyone.
    - Manager: themselves, plus anyone in their own ``managed_user_ids()``.
    - Employee: themselves only (their own profile is their own data; the
      Employee UI does not surface this, but the rule must hold at the
      data layer regardless of what any UI shows).
    """
    from apps.crm.services import managed_user_ids

    if requesting_user is None or not getattr(requesting_user, "is_authenticated", False):
        return False
    if is_super_admin(requesting_user):
        return True
    if requesting_user.pk == target_user.pk:
        return True
    if user_has_role_at_least(requesting_user, User.Role.MANAGER):
        return target_user.pk in managed_user_ids(requesting_user)
    return False


def _basic_profile(user):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name or user.email,
        "phone": user.phone,
        "department": user.department,
        "role": user.role,
        "date_joined": user.date_joined,
        "is_active": user.is_active,
    }


def _lead_performance(user, *, now=None):
    """Lead counts for ``user`` as the lead OWNER: all-time assigned,
    assigned this calendar month, converted, and the conversion rate.
    """
    from apps.crm.models import Lead

    now = now or timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    aggregates = Lead.active_objects.filter(owner=user).aggregate(
        total_assigned=Count("id"),
        assigned_this_month=Count("id", filter=Q(created_at__gte=month_start)),
        converted=Count("id", filter=Q(converted_customer__isnull=False)),
    )
    total = aggregates["total_assigned"] or 0
    converted = aggregates["converted"] or 0
    by_status = {
        row["status"]: row["count"]
        for row in Lead.active_objects.filter(owner=user).values("status").annotate(count=Count("id"))
    }
    return {
        "total_assigned": total,
        "assigned_this_month": aggregates["assigned_this_month"] or 0,
        "converted": converted,
        "conversion_rate": round((converted / total) * 100, 2) if total else 0.0,
        "by_status": by_status,
    }


def _converted_customers(user, *, limit=50):
    """Customers this user converted a lead into (linked through
    ``Lead.converted_customer``), newest first — profile, conversion date,
    and payment status derived from the customer's own invoices.
    """
    from apps.crm.models import Lead
    from apps.sales.models import Invoice

    leads = (
        Lead.active_objects.filter(owner=user, converted_customer__isnull=False)
        .select_related("converted_customer")
        .order_by("-updated_at")[:limit]
    )
    results = []
    for lead in leads:
        customer = lead.converted_customer
        invoices = Invoice.active_objects.filter(customer=customer)
        overdue = invoices.overdue().exists()
        unpaid = invoices.exclude(status=Invoice.Status.PAID).exists()
        if overdue:
            payment_status = "OVERDUE"
        elif unpaid:
            payment_status = "OUTSTANDING"
        elif invoices.exists():
            payment_status = "PAID"
        else:
            payment_status = "NO_INVOICES"
        results.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "lead_id": lead.id,
                "converted_at": lead.updated_at,
                "payment_status": payment_status,
            }
        )
    return results


def _interaction_history(user, *, limit=50):
    """This user's communication trail — calls, WhatsApp, emails, meetings,
    notes, follow-ups — read from ``CommunicationLog``, the model that
    already records every one of them (see ``apps.communications``).
    """
    from apps.communications.models import CommunicationLog

    logs = (
        CommunicationLog.active_objects.filter(actor=user)
        .select_related("content_type")
        .order_by("-occurred_at")[:limit]
    )
    return [
        {
            "id": log.id,
            "channel": log.channel,
            "summary": log.summary,
            "occurred_at": log.occurred_at,
            "related_type": log.content_type.model if log.content_type_id else None,
            "related_id": log.object_id,
        }
        for log in logs
    ]


def _work_activity(user, *, limit=25):
    """Tasks, follow-ups (reminders), and calendar events owned by this
    user, plus today's attendance summary — the "Work activity" block.
    """
    from apps.activities.models import Event, Task
    from apps.attendance.services import compute_daily_summary

    tasks = Task.active_objects.filter(owner=user)
    open_tasks = tasks.exclude(status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED])
    upcoming_events = Event.active_objects.filter(owner=user, start_at__gte=timezone.now()).order_by("start_at")

    return {
        "task_counts": {
            "total": tasks.count(),
            "open": open_tasks.count(),
            "completed": tasks.filter(status=Task.Status.COMPLETED).count(),
            "overdue": open_tasks.filter(due_date__lt=timezone.now()).count(),
        },
        "upcoming_events": [
            {"id": event.id, "title": event.title, "start_at": event.start_at, "location": event.location}
            for event in upcoming_events[:limit]
        ],
        "attendance_today": compute_daily_summary(user, timezone.localdate()),
    }


def _managed_employees(manager):
    """The employees this Manager oversees (via ``apps.organization``
    Team/Membership) — list, count, status. Empty for a non-Manager.
    """
    from apps.crm.services import managed_user_ids

    member_ids = {uid for uid in managed_user_ids(manager) if uid != manager.pk}
    members = User.objects.filter(pk__in=member_ids).order_by("email")
    return [
        {
            "id": member.id,
            "full_name": member.full_name or member.email,
            "email": member.email,
            "role": member.role,
            "is_active": member.is_active,
        }
        for member in members
    ]


def _manager_scope_lead_stats(manager):
    """Leads across a Manager's whole scope: assigned TO the manager
    directly, assigned BY the manager to their team (i.e. owned by a team
    member), and how many of each converted.
    """
    from apps.crm.models import Lead
    from apps.crm.services import managed_user_ids

    team_ids = {uid for uid in managed_user_ids(manager) if uid != manager.pk}
    own = Lead.active_objects.filter(owner=manager)
    team = Lead.active_objects.filter(owner_id__in=team_ids)
    scope_total = own.count() + team.count()
    scope_converted = own.converted().count() + team.converted().count()
    return {
        "assigned_to_manager": own.count(),
        "assigned_to_team": team.count(),
        "converted_in_scope": scope_converted,
        "scope_conversion_rate": round((scope_converted / scope_total) * 100, 2) if scope_total else 0.0,
    }


def build_staff_profile(user):
    """The full profile payload for ``user``.

    Shape is role-aware: a MANAGER additionally gets ``managed_employees``
    and ``scope_lead_stats``; every role gets the same basic/lead/customer/
    interaction/work-activity blocks, so a frontend never has to branch on
    role just to find a field.
    """
    payload = {
        "profile": _basic_profile(user),
        "lead_performance": _lead_performance(user),
        "converted_customers": _converted_customers(user),
        "interaction_history": _interaction_history(user),
        "work_activity": _work_activity(user),
        "managed_employees": [],
        "scope_lead_stats": None,
    }
    if user.role == User.Role.MANAGER:
        payload["managed_employees"] = _managed_employees(user)
        payload["scope_lead_stats"] = _manager_scope_lead_stats(user)
    return payload


__all__ = ["can_view_staff_profile", "build_staff_profile"]
