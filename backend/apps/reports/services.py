"""CP16: reusable service functions for the reporting/dashboard domain.

Ownership scoping is NOT reimplemented — CP10's `managed_user_ids()`/
`scope_queryset_for_user()` are imported directly from `apps.crm.services`,
the same reuse every checkpoint since CP12 has applied.

`execute_report()` is CP16's "report execution abstraction": a small
dispatch table (`_REPORT_COMPUTERS`) maps each `SavedReport.ReportType` to
its own compute function, each of which queries an EXISTING domain
model — `apps.crm.models.Lead` (CP9), `apps.crm.opportunities.Opportunity`
(CP11), `apps.activities.models.Task`/`ActivityLog` (CP14) — rather than
this app maintaining its own duplicate copy of lead/opportunity/activity
data. Reports compute FROM the domain, they do not re-store it.
"""
from django.db.models import Count, Max, Sum
from django.utils import timezone

from apps.crm.services import managed_user_ids, scope_queryset_for_user  # noqa: F401 (re-exported)

from .models import Dashboard, DashboardWidget, ReportExecution, SavedReport

# --------------------------------------------------------------------------
# SavedReport
# --------------------------------------------------------------------------


def create_saved_report(name, report_type, *, owner=None, description="", filters=None):
    """Create a `SavedReport`. A thin wrapper — kept as a service function
    for the same single-seam reasoning as CP9's `create_lead()`.
    """
    return SavedReport.objects.create(
        name=name, report_type=report_type, owner=owner, description=description, filters=filters or {}
    )


# --------------------------------------------------------------------------
# Report execution abstraction
# --------------------------------------------------------------------------

#: Every compute function has the same shape: ``(filters: dict) -> dict``,
#: returning ``{"rows": [...], "summary": {...}}`` — a consistent envelope
#: regardless of report type, so callers/serializers never need to branch
#: on ``report_type`` to know how to read ``result_data``.
_REPORT_COMPUTERS = {}


def _register(report_type):
    def decorator(func):
        _REPORT_COMPUTERS[report_type] = func
        return func

    return decorator


@_register(SavedReport.ReportType.PRODUCTIVITY)
def _compute_productivity(filters):
    """Per-user counts of completed `Task`s and logged `ActivityLog`
    entries (both CP14) — the "Employee activity tracking"/"Productivity
    reports" client requirements this checkpoint fulfills. Optional
    `filters`: ``date_from``/``date_to`` (ISO datetimes), ``owner_id``.
    """
    from apps.activities.models import ActivityLog, Task

    tasks = Task.active_objects.filter(status=Task.Status.COMPLETED)
    logs = ActivityLog.active_objects.all()

    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    if date_from:
        tasks = tasks.filter(completed_at__gte=date_from)
        logs = logs.filter(occurred_at__gte=date_from)
    if date_to:
        tasks = tasks.filter(completed_at__lte=date_to)
        logs = logs.filter(occurred_at__lte=date_to)

    owner_id = filters.get("owner_id")
    if owner_id:
        tasks = tasks.filter(assigned_to_id=owner_id)
        logs = logs.filter(actor_id=owner_id)

    tasks_by_user = {
        row["assigned_to"]: row["count"]
        for row in tasks.values("assigned_to").annotate(count=Count("id"))
        if row["assigned_to"] is not None
    }
    logs_by_user = {
        row["actor"]: row["count"]
        for row in logs.values("actor").annotate(count=Count("id"))
        if row["actor"] is not None
    }

    user_ids = sorted(set(tasks_by_user) | set(logs_by_user))
    rows = [
        {
            "user_id": user_id,
            "tasks_completed": tasks_by_user.get(user_id, 0),
            "activities_logged": logs_by_user.get(user_id, 0),
        }
        for user_id in user_ids
    ]
    return {
        "rows": rows,
        "summary": {
            "total_tasks_completed": sum(tasks_by_user.values()),
            "total_activities_logged": sum(logs_by_user.values()),
        },
    }


@_register(SavedReport.ReportType.LEAD_CONVERSION)
def _compute_lead_conversion(filters):
    """Lead volume and conversion rate (CP9's `Lead.converted_customer`).
    Optional `filters`: ``date_from``/``date_to``, ``owner_id``.
    """
    from apps.crm.models import Lead

    leads = Lead.active_objects.all()

    date_from = filters.get("date_from")
    date_to = filters.get("date_to")
    if date_from:
        leads = leads.filter(created_at__gte=date_from)
    if date_to:
        leads = leads.filter(created_at__lte=date_to)

    owner_id = filters.get("owner_id")
    if owner_id:
        leads = leads.filter(owner_id=owner_id)

    total = leads.count()
    converted = leads.filter(converted_customer__isnull=False).count()
    rate = round(converted / total * 100, 2) if total else 0.0

    return {
        "rows": [],
        "summary": {"total_leads": total, "converted_leads": converted, "conversion_rate_pct": rate},
    }


@_register(SavedReport.ReportType.SALES_PIPELINE)
def _compute_sales_pipeline(filters):
    """Open `Opportunity` (CP11) count/value grouped by stage. Optional
    `filters`: ``owner_id``.
    """
    from apps.crm.opportunities import Opportunity

    opportunities = Opportunity.active_objects.filter(is_closed=False)

    owner_id = filters.get("owner_id")
    if owner_id:
        opportunities = opportunities.filter(owner_id=owner_id)

    by_stage = opportunities.values("stage").annotate(count=Count("id"), total_value=Sum("value"))
    rows = [
        {"stage": row["stage"], "count": row["count"], "total_value": str(row["total_value"] or 0)}
        for row in by_stage
    ]
    return {"rows": rows, "summary": {"open_opportunity_count": opportunities.count()}}


@_register(SavedReport.ReportType.CUSTOMER_ACTIVITY)
def _compute_customer_activity(filters):
    """`ActivityLog` (CP14) count per `Customer`, using the SAME
    `content_type`/`object_id` generic relation CP14 built — no new
    "which customer is this about" logic.
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.activities.models import ActivityLog
    from apps.crm.models import Customer

    customer_content_type = ContentType.objects.get_for_model(Customer)
    logs = ActivityLog.active_objects.filter(content_type=customer_content_type)

    by_customer = logs.values("object_id").annotate(count=Count("id")).order_by("-count")
    rows = [{"customer_id": row["object_id"], "activity_count": row["count"]} for row in by_customer]
    return {"rows": rows, "summary": {"total_activities": logs.count()}}


@_register(SavedReport.ReportType.CUSTOM)
def _compute_custom(filters):
    """No built-in computation — `CUSTOM` is an explicit extension point
    (see `BACKEND_LEARNING_GUIDE.md` CP16), not a fallback for an
    unrecognized type. Always succeeds with an empty result rather than
    raising, since "custom, nothing computed yet" is a valid, expected
    state, not an error.
    """
    return {"rows": [], "summary": {}}


def execute_report(report, *, executed_by=None):
    """Run `report` and return the `ReportExecution` recording what
    happened — COMPLETED with `result_data`/`row_count` set, or FAILED
    with `error_message` set. Never raises: an exception from the
    underlying compute function is caught and recorded on the execution,
    the same "a failure is a recorded fact, not a crash" contract CP15's
    `send_queued_email()` established.
    """
    execution = ReportExecution.objects.create(
        report=report, executed_by=executed_by, status=ReportExecution.Status.RUNNING, started_at=timezone.now()
    )

    compute = _REPORT_COMPUTERS[report.report_type]
    try:
        result = compute(report.filters or {})
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any compute failure is "FAILED", not a crash
        execution.status = ReportExecution.Status.FAILED
        execution.error_message = str(exc)
        execution.completed_at = timezone.now()
        execution.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
        return execution

    execution.status = ReportExecution.Status.COMPLETED
    execution.result_data = result
    execution.row_count = len(result.get("rows", []))
    execution.completed_at = timezone.now()
    execution.save(update_fields=["status", "result_data", "row_count", "completed_at", "updated_at"])
    return execution


# --------------------------------------------------------------------------
# Dashboard management
# --------------------------------------------------------------------------


def create_dashboard(name, *, owner=None, is_default=False):
    """Create a `Dashboard`. If `is_default=True`, demotes `owner`'s
    existing default dashboard first — without this, creating a second
    default would simply fail against the DB's partial unique constraint
    (see `models.py`). Same "promote a new primary, demote the old one in
    the same call" shape as CP9's `add_contact(is_primary=True)`.
    """
    if is_default and owner is not None:
        Dashboard.objects.filter(owner=owner, is_default=True).update(is_default=False)
    return Dashboard.objects.create(name=name, owner=owner, is_default=is_default)


def set_default_dashboard(dashboard):
    """Promote `dashboard` to be its owner's default, demoting whichever
    dashboard (if any) previously held that spot. Same demote-then-promote
    reasoning as `create_dashboard(is_default=True)`, as its own callable
    step for an ALREADY-EXISTING dashboard.
    """
    Dashboard.objects.filter(owner=dashboard.owner, is_default=True).exclude(pk=dashboard.pk).update(
        is_default=False
    )
    dashboard.is_default = True
    dashboard.save(update_fields=["is_default", "updated_at"])
    return dashboard


# --------------------------------------------------------------------------
# Widget configuration
# --------------------------------------------------------------------------


def add_widget(dashboard, report, widget_type, title, *, position=None, configuration=None):
    """Add a `DashboardWidget` to `dashboard`. Auto-assigns `position`
    (one past the current highest) when omitted — same auto-ordering
    convenience CP12's `add_quote_item()`/`add_invoice_item()` established.
    """
    if position is None:
        highest = DashboardWidget.objects.filter(dashboard=dashboard).aggregate(Max("position"))["position__max"]
        position = 0 if highest is None else highest + 1
    return DashboardWidget.objects.create(
        dashboard=dashboard, report=report, widget_type=widget_type, title=title, position=position,
        configuration=configuration or {},
    )


def update_widget_configuration(widget, configuration):
    """Replace `widget.configuration` wholesale. A thin wrapper — kept as
    a service function (rather than a bare field assignment at call
    sites) so a future validation rule for widget configs has one seam,
    same reasoning as CP9's `add_address()`.
    """
    widget.configuration = configuration
    widget.save(update_fields=["configuration", "updated_at"])
    return widget


# --------------------------------------------------------------------------
# Company-wide dashboard summary (Reports/Payments audit pass)
# --------------------------------------------------------------------------


def _period_stats(*, date_from=None, date_to=None):
    """One period's worth of the six company-wide dashboard metrics —
    Total Leads, Total Converted Leads, Total Revenue, Pending Payments,
    Active Employees, Conversion Rate — computed server-side from the
    real domain models (never frontend-aggregated). Shared by both the
    "This Month" and "All Time" sections below so the two can never drift
    out of sync in how a metric is defined; only the date bounds differ.

    ``date_from``/``date_to`` bound the *activity* each metric counts
    (a lead created, a lead converted, a payment received) — ``None``
    means unbounded, i.e. "All Time". Pending Payments and Active
    Employees are current-state snapshots by nature (a balance still
    owed, a currently-active account), so they are reported as of NOW
    for both sections rather than artificially bounded to a period a
    balance may have existed across — see the return value's own keys
    for exactly what each number means.
    """
    from django.db.models import DecimalField, Q, Sum, Value
    from django.db.models.functions import Coalesce

    from apps.accounts.models import User
    from apps.crm.models import Lead

    def _bounded(queryset, field):
        if date_from is not None:
            queryset = queryset.filter(**{f"{field}__gte": date_from})
        if date_to is not None:
            queryset = queryset.filter(**{f"{field}__lt": date_to})
        return queryset

    leads = _bounded(Lead.active_objects.all(), "created_at")
    total_leads = leads.count()

    converted_leads = _bounded(
        Lead.active_objects.filter(status=Lead.Status.CONVERTED, converted_customer__isnull=False),
        "converted_customer__created_at",
    ).count()

    try:
        from apps.sales.models import Invoice, PaymentTransaction

        revenue_qs = _bounded(PaymentTransaction.active_objects.all(), "paid_at")
        total_revenue = revenue_qs.aggregate(
            total=Coalesce(Sum("amount"), Value(0), output_field=DecimalField(max_digits=14, decimal_places=2))
        )["total"]

        # Pending Payments is a current-state balance (what is owed RIGHT
        # NOW on every not-cancelled invoice), reported identically for
        # both sections — a payment made last month can still be part of
        # this month's pending picture, so bounding it by period would
        # misrepresent what is actually still owed.
        outstanding = Invoice.active_objects.exclude(status=Invoice.Status.CANCELLED).annotate(
            _paid=Coalesce(
                Sum("payments__amount", filter=Q(payments__is_deleted=False)),
                Value(0),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )
        pending_payments = sum((invoice.total - invoice._paid) for invoice in outstanding)
    except Exception:  # pragma: no cover - defensive only; apps.sales always installed
        total_revenue = 0
        pending_payments = 0

    # Active Employees: current active Employee/Manager headcount for
    # "All Time"; for "This Month" (date_from set), narrowed to those who
    # actually logged an attendance session inside the period — an
    # employee who never worked this month is not meaningfully "active
    # this month" even if their account is still enabled.
    staff = User.objects.filter(is_active=True, role__in=[User.Role.EMPLOYEE, User.Role.MANAGER])
    if date_from is not None:
        from apps.attendance.models import AttendanceSession

        worked_ids = _bounded(AttendanceSession.active_objects.all(), "login_at").values_list(
            "employee_id", flat=True
        )
        staff = staff.filter(pk__in=set(worked_ids))
    active_employees = staff.count()

    conversion_rate = round((converted_leads / total_leads) * 100, 1) if total_leads else 0.0

    return {
        "total_leads": total_leads,
        "total_converted_leads": converted_leads,
        "total_revenue": total_revenue,
        "pending_payments": pending_payments,
        "active_employees": active_employees,
        "conversion_rate": conversion_rate,
    }


def compute_company_dashboard_summary(*, now=None):
    """``{"this_month": {...}, "all_time": {...}}`` — the Super Admin
    Reports/Dashboard's two clearly-separated sections (Revenue/Reports
    audit pass). Both blocks use the exact same six-metric shape from
    ``_period_stats()`` above; only the date bounds differ, so a client
    never needs its own aggregation logic to render either section.
    """
    now = now or timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)

    return {
        "this_month": _period_stats(date_from=month_start, date_to=next_month_start),
        "all_time": _period_stats(),
    }


__all__ = [
    "managed_user_ids",
    "scope_queryset_for_user",
    "create_saved_report",
    "execute_report",
    "create_dashboard",
    "set_default_dashboard",
    "add_widget",
    "update_widget_configuration",
    "compute_company_dashboard_summary",
]
