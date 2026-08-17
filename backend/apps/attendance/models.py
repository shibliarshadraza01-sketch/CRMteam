"""Employee working-hours / attendance time tracking.

    ShiftConfiguration (one row, company-wide — single-tenant, no
        per-employee/per-team shift variation in this pass)
    AttendanceSession --< TimeSegment

Every model inherits ``apps.core.models.SoftDeleteTimeStampedModel``
(the same pattern every CP9+ domain model in this project uses) — an
attendance record is exactly the kind of thing a correction should
reversibly soft-delete, never permanently erase (payroll/compliance
data).

The core accuracy rule this whole app exists to enforce (see each
model's own docstring for how): LOGIN TIME != ACTIVE WORKING TIME.
``AttendanceSession.login_at``/``logout_at`` record when the session
existed; ``TimeSegment`` rows are the actual ledger of what happened
inside it (WORK/BREAK/IDLE/OFFLINE), and everything payroll-relevant
(``services.compute_session_totals()``) is summed from THAT ledger, not
from the login/logout timestamps.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteQuerySet, SoftDeleteTimeStampedModel


class ShiftConfiguration(SoftDeleteTimeStampedModel):
    """Company-wide shift/attendance policy — Super Admin configurable
    (see ``views.ShiftConfigurationViewSet``). Deliberately a single
    row for the whole company: this project is explicitly single-
    tenant/single-company (see PRODUCTION_DEPLOYMENT_GUIDE.md — "no
    multi-tenancy"), so there is exactly one shift policy, not one per
    team/employee. ``services.get_active_shift_configuration()`` is the
    one place that row is looked up — see that function's own docstring
    for how a missing row is handled (a hardcoded fallback default, not
    an error, since every employee needs SOME policy to be timed against
    even before a Super Admin has ever opened Settings).
    """

    shift_duration_minutes = models.PositiveIntegerField(
        _("shift duration (minutes)"), default=540, help_text=_("Standard shift length — 540 = 9 hours.")
    )
    shift_start_time = models.TimeField(_("shift start time"), null=True, blank=True)
    shift_end_time = models.TimeField(_("shift end time"), null=True, blank=True)
    allowed_break_minutes = models.PositiveIntegerField(_("allowed break (minutes)"), default=60)
    idle_timeout_minutes = models.PositiveIntegerField(
        _("idle timeout (minutes)"), default=5,
        help_text=_("No heartbeat for longer than this closes the current WORK segment and opens an IDLE one."),
    )
    overtime_threshold_minutes = models.PositiveIntegerField(
        _("overtime threshold (minutes)"), default=0,
        help_text=_("Active minutes beyond shift_duration_minutes + this threshold count as overtime."),
    )
    is_salary_enabled = models.BooleanField(_("salary calculation enabled"), default=False)
    hourly_rate = models.DecimalField(_("hourly rate"), max_digits=10, decimal_places=2, default=0)
    overtime_multiplier = models.DecimalField(
        _("overtime multiplier"), max_digits=4, decimal_places=2, default=1.5,
        help_text=_("Overtime hours are paid at hourly_rate * this multiplier."),
    )
    currency = models.CharField(_("currency"), max_length=8, default="USD")

    objects = models.Manager.from_queryset(SoftDeleteQuerySet)()
    active_objects = objects

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("shift configuration")
        verbose_name_plural = _("shift configurations")

    def __str__(self):
        return f"Shift policy ({self.shift_duration_minutes}min)"


class AttendanceSessionQuerySet(SoftDeleteQuerySet):
    def for_employee(self, user):
        return self.filter(employee=user)

    def open(self):
        return self.filter(logout_at__isnull=True)


class AttendanceSessionManager(models.Manager.from_queryset(AttendanceSessionQuerySet)):
    """``AttendanceSession.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveAttendanceSessionManager(AttendanceSessionManager):
    def get_queryset(self):
        return super().get_queryset().active()


class AttendanceSession(SoftDeleteTimeStampedModel):
    """One login-to-logout working session. ``state``/``last_heartbeat_at``
    are the live, real-time-status fields (see
    ``services.compute_display_state()``); the durable, payroll-relevant
    numbers are always derived from this session's ``segments`` (see
    ``services.compute_session_totals()``), never stored redundantly
    here — the same "derived, never hand-edited" rule this project
    already applies to ``Invoice.amount_paid``/``InvoiceItem.total_price``.
    """

    class State(models.TextChoices):
        WORKING = "WORKING", _("Working")
        ON_BREAK = "ON_BREAK", _("On Break")
        OFFLINE = "OFFLINE", _("Offline")

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("employee"),
        on_delete=models.CASCADE,
        related_name="attendance_sessions",
    )
    login_at = models.DateTimeField(_("login at"))
    logout_at = models.DateTimeField(_("logout at"), null=True, blank=True)
    state = models.CharField(_("state"), max_length=10, choices=State.choices, default=State.WORKING, db_index=True)
    last_heartbeat_at = models.DateTimeField(_("last heartbeat at"))

    objects = AttendanceSessionManager()
    active_objects = ActiveAttendanceSessionManager()

    class Meta:
        ordering = ["-login_at"]
        verbose_name = _("attendance session")
        verbose_name_plural = _("attendance sessions")
        indexes = [
            models.Index(fields=["employee", "login_at"], name="attend_sess_emp_login_idx"),
            models.Index(fields=["employee", "logout_at"], name="attend_sess_emp_logout_idx"),
        ]

    def __str__(self):
        return f"{self.employee_id} @ {self.login_at:%Y-%m-%d %H:%M}"

    @property
    def owner(self):
        """Lets ``IsOwnerOrSuperAdmin`` find this session's owning user —
        the same delegation-by-property pattern CP9's ``ContactPerson.owner``
        established, applied here to a real (not delegated) FK for
        clarity even though a plain ``owner_field = "employee"`` on the
        viewset would also work — kept as a property so services.py
        functions that only have the session (not the viewset) can also
        resolve it uniformly.
        """
        return self.employee

    def manager_has_access(self, user):
        from apps.crm.services import managed_user_ids

        return self.employee_id in managed_user_ids(user)


class TimeSegmentQuerySet(SoftDeleteQuerySet):
    def for_session(self, session):
        return self.filter(session=session)

    def of_type(self, segment_type):
        return self.filter(segment_type=segment_type)


class TimeSegmentManager(models.Manager.from_queryset(TimeSegmentQuerySet)):
    """``TimeSegment.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveTimeSegmentManager(TimeSegmentManager):
    def get_queryset(self):
        return super().get_queryset().active()


class TimeSegment(SoftDeleteTimeStampedModel):
    """One contiguous block of time within an ``AttendanceSession``,
    labeled by what was actually happening — WORK, BREAK (explicit,
    employee-initiated), IDLE (detected: no heartbeat for longer than
    ``ShiftConfiguration.idle_timeout_minutes`` — covers inactivity,
    laptop sleep/lock, tab-away, and network loss uniformly, since all
    of them look identical from the server's point of view: heartbeats
    simply stopped arriving for a while). ``ended_at`` is null while the
    segment is still open (the current, in-progress one) — exactly one
    segment per session should ever be open at a time; see
    ``services.py`` for the state machine that enforces this.
    """

    class SegmentType(models.TextChoices):
        WORK = "WORK", _("Work")
        BREAK = "BREAK", _("Break")
        IDLE = "IDLE", _("Idle")

    session = models.ForeignKey(
        AttendanceSession, verbose_name=_("session"), on_delete=models.CASCADE, related_name="segments"
    )
    segment_type = models.CharField(_("type"), max_length=8, choices=SegmentType.choices, db_index=True)
    started_at = models.DateTimeField(_("started at"))
    ended_at = models.DateTimeField(_("ended at"), null=True, blank=True)

    objects = TimeSegmentManager()
    active_objects = ActiveTimeSegmentManager()

    class Meta:
        ordering = ["session", "started_at"]
        verbose_name = _("time segment")
        verbose_name_plural = _("time segments")
        indexes = [
            models.Index(fields=["session", "segment_type"], name="attendance_segment_type_idx"),
        ]

    def __str__(self):
        return f"{self.segment_type} {self.started_at:%H:%M} -> {self.ended_at:%H:%M}" if self.ended_at else f"{self.segment_type} {self.started_at:%H:%M} (open)"

    @property
    def owner(self):
        return self.session.employee

    def manager_has_access(self, user):
        return self.session.manager_has_access(user)
