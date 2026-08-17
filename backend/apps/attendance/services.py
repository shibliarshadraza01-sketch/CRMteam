"""Attendance/working-hours business logic — the ONLY place session
state transitions, idle detection, and payroll-relevant totals are
computed. Every timestamp used for a decision is a SERVER timestamp
(``django.utils.timezone.now()`` unless a test passes one explicitly) —
nothing here ever trusts a client-supplied time, which is the whole
point of the "server-side heartbeats so employees cannot manipulate the
timer" requirement this app exists to satisfy.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import AttendanceSession, ShiftConfiguration, TimeSegment

DEFAULT_SHIFT_DURATION_MINUTES = 540  # 9 hours
DEFAULT_IDLE_TIMEOUT_MINUTES = 5
DEFAULT_ALLOWED_BREAK_MINUTES = 60


def get_active_shift_configuration():
    """The single, company-wide shift policy row (see ``models.py``'s
    own docstring for why this project has exactly one, not one per
    team/employee). Auto-creates a sensible-default row on first access
    rather than raising — every employee needs SOME policy to be timed
    against even before a Super Admin has ever opened the attendance
    settings screen, the same "a real default beats an error" reasoning
    ``config/settings/development.py`` already applies to its own
    fallback ``DJANGO_SECRET_KEY``.
    """
    config = ShiftConfiguration.active_objects.order_by("-created_at").first()
    if config is not None:
        return config
    return ShiftConfiguration.objects.create(
        shift_duration_minutes=DEFAULT_SHIFT_DURATION_MINUTES,
        idle_timeout_minutes=DEFAULT_IDLE_TIMEOUT_MINUTES,
        allowed_break_minutes=DEFAULT_ALLOWED_BREAK_MINUTES,
    )


@transaction.atomic
def start_session(employee, *, now=None):
    """Begin a new working session for ``employee`` — called by the
    frontend immediately after a successful login (never by the login
    view itself; see this app's own integration note in
    ``BACKEND_PROGRESS.md`` — auth is explicitly not modified).

    Any previously OPEN session for this same employee is closed first
    (state OFFLINE, logout_at=now) — handles "multiple login sessions"
    (a second tab/device logging in, a browser crash that never called
    ``end_session``) without ever leaving two sessions open and double-
    counting the same wall-clock time across both.
    """
    now = now or timezone.now()

    stale_sessions = AttendanceSession.active_objects.for_employee(employee).open()
    for stale in stale_sessions:
        end_session(stale, now=now)

    session = AttendanceSession.objects.create(
        employee=employee, login_at=now, last_heartbeat_at=now, state=AttendanceSession.State.WORKING
    )
    TimeSegment.objects.create(session=session, segment_type=TimeSegment.SegmentType.WORK, started_at=now)
    return session


def _open_segment(session):
    return session.segments.active().filter(ended_at__isnull=True).order_by("-started_at").first()


@transaction.atomic
def record_heartbeat(session, *, now=None):
    """Called by the frontend every ~20-30s while the employee is
    considered locally active (see the frontend's own idle-detection
    logic — the CLIENT decides when to stop sending heartbeats based on
    mouse/keyboard activity; the SERVER decides, independently, whether
    the resulting gap counts as idle). This dual design is what makes a
    single mechanism cover BOTH "no mouse/keyboard activity for 5
    minutes" (Part 4) AND "laptop slept/locked/lost network" (Part 5,
    Part 6) — from the server's perspective they're indistinguishable
    (heartbeats simply stopped), which is exactly why the spec asked for
    both to be handled the same way.

    If the gap since the last heartbeat exceeds
    ``ShiftConfiguration.idle_timeout_minutes`` AND the session was
    ``WORKING`` (not on an explicit break — a break's own gap is
    expected and handled by ``start_break()``/``end_break()`` instead),
    the open WORK segment is closed AT THE LAST KNOWN HEARTBEAT time
    (not now — that's the last moment we actually know they were
    active), an IDLE segment is recorded for the gap, and a new WORK
    segment starts now.
    """
    now = now or timezone.now()
    config = get_active_shift_configuration()
    idle_threshold = timedelta(minutes=config.idle_timeout_minutes)
    gap = now - session.last_heartbeat_at

    if session.state == AttendanceSession.State.WORKING and gap > idle_threshold:
        open_segment = _open_segment(session)
        if open_segment is not None and open_segment.segment_type == TimeSegment.SegmentType.WORK:
            open_segment.ended_at = session.last_heartbeat_at
            open_segment.save(update_fields=["ended_at", "updated_at"])
        TimeSegment.objects.create(
            session=session,
            segment_type=TimeSegment.SegmentType.IDLE,
            started_at=session.last_heartbeat_at,
            ended_at=now,
        )
        TimeSegment.objects.create(session=session, segment_type=TimeSegment.SegmentType.WORK, started_at=now)
    elif _open_segment(session) is None:
        # Defensive: a session should always have exactly one open
        # segment while active. Recreate one if it's somehow missing
        # rather than silently under-counting from here on.
        segment_type = TimeSegment.SegmentType.BREAK if session.state == AttendanceSession.State.ON_BREAK else TimeSegment.SegmentType.WORK
        TimeSegment.objects.create(session=session, segment_type=segment_type, started_at=now)

    session.last_heartbeat_at = now
    session.save(update_fields=["last_heartbeat_at", "updated_at"])
    return session


@transaction.atomic
def start_break(session, *, now=None):
    """Employee-initiated break — closes the open WORK segment, opens a
    BREAK segment. Raises ``ValueError`` if the session isn't currently
    WORKING (already offline, or already on a break).
    """
    if session.state != AttendanceSession.State.WORKING:
        raise ValueError(f"Cannot start a break from state {session.state}.")
    now = now or timezone.now()

    open_segment = _open_segment(session)
    if open_segment is not None:
        open_segment.ended_at = now
        open_segment.save(update_fields=["ended_at", "updated_at"])

    TimeSegment.objects.create(session=session, segment_type=TimeSegment.SegmentType.BREAK, started_at=now)
    session.state = AttendanceSession.State.ON_BREAK
    session.last_heartbeat_at = now
    session.save(update_fields=["state", "last_heartbeat_at", "updated_at"])
    return session


@transaction.atomic
def end_break(session, *, now=None):
    """Resume work — closes the open BREAK segment, opens a new WORK
    segment. "Resume → Working timer continues from where it left off"
    (Part 3) is automatic here: the WORK total is a SUM of every WORK
    segment, so a new one simply adds to the running total rather than
    resetting anything.
    """
    if session.state != AttendanceSession.State.ON_BREAK:
        raise ValueError(f"Cannot end a break from state {session.state}.")
    now = now or timezone.now()

    open_segment = _open_segment(session)
    if open_segment is not None:
        open_segment.ended_at = now
        open_segment.save(update_fields=["ended_at", "updated_at"])

    TimeSegment.objects.create(session=session, segment_type=TimeSegment.SegmentType.WORK, started_at=now)
    session.state = AttendanceSession.State.WORKING
    session.last_heartbeat_at = now
    session.save(update_fields=["state", "last_heartbeat_at", "updated_at"])
    return session


@transaction.atomic
def end_session(session, *, now=None):
    """Logout — closes whatever segment is currently open (WORK or
    BREAK) and marks the session OFFLINE. Idempotent: calling this on
    an already-closed session is a no-op (returns it unchanged) rather
    than raising — a duplicate logout request (e.g. browser retry)
    must never double-close or corrupt an already-finalized session.
    """
    if session.logout_at is not None:
        return session
    now = now or timezone.now()

    open_segment = _open_segment(session)
    if open_segment is not None:
        open_segment.ended_at = now
        open_segment.save(update_fields=["ended_at", "updated_at"])

    session.logout_at = now
    session.state = AttendanceSession.State.OFFLINE
    session.last_heartbeat_at = now
    session.save(update_fields=["logout_at", "state", "last_heartbeat_at", "updated_at"])
    return session


def compute_session_totals(session, *, now=None):
    """The core accuracy rule (Part 14), applied: sums ONLY from the
    ``TimeSegment`` ledger, never ``logout_at - login_at``. The
    currently-open segment (if the session is still active) is included
    up to ``now`` so a live dashboard reads correctly mid-session, not
    just after logout.
    """
    now = now or timezone.now()
    work_seconds = 0
    break_seconds = 0
    idle_seconds = 0
    break_count = 0

    for segment in session.segments.active().order_by("started_at"):
        end = segment.ended_at or now
        duration = max((end - segment.started_at).total_seconds(), 0)
        if segment.segment_type == TimeSegment.SegmentType.WORK:
            work_seconds += duration
        elif segment.segment_type == TimeSegment.SegmentType.BREAK:
            break_seconds += duration
            break_count += 1
        elif segment.segment_type == TimeSegment.SegmentType.IDLE:
            idle_seconds += duration

    session_end = session.logout_at or now
    session_seconds = max((session_end - session.login_at).total_seconds(), 0)

    return {
        "session_seconds": int(session_seconds),
        "active_working_seconds": int(work_seconds),
        "break_seconds": int(break_seconds),
        "idle_seconds": int(idle_seconds),
        "break_count": break_count,
    }


def compute_display_state(session, *, config=None, now=None):
    """Real-time status (Part 13) — WORKING / ON_BREAK / IDLE / OFFLINE.
    Computed at READ time from ``last_heartbeat_at``, not stored: an
    employee who has gone idle but hasn't sent their next heartbeat yet
    (which is what would normally finalize the IDLE segment) should
    still show as Idle to a Manager/Super Admin watching in real time,
    not "Working" until they happen to come back.
    """
    if session is None or session.logout_at is not None:
        return AttendanceSession.State.OFFLINE
    if session.state == AttendanceSession.State.ON_BREAK:
        return AttendanceSession.State.ON_BREAK

    now = now or timezone.now()
    config = config or get_active_shift_configuration()
    idle_threshold = timedelta(minutes=config.idle_timeout_minutes)
    if now - session.last_heartbeat_at > idle_threshold:
        return "IDLE"
    return AttendanceSession.State.WORKING


def calculate_earnings(active_seconds, *, config=None):
    """Earnings computed ONLY from active working time (Part 9) — never
    from session/login-logout duration. Regular pay covers up to
    ``shift_duration_minutes + overtime_threshold_minutes``; anything
    beyond that is overtime, paid at ``hourly_rate * overtime_multiplier``.
    Returns Decimal-safe floats rounded to 2 places; ``regular_earnings``
    is 0 whenever ``config.is_salary_enabled`` is False, but the minute
    breakdown is still returned (useful for a dashboard even with
    salary calculation turned off).
    """
    config = config or get_active_shift_configuration()
    active_minutes = active_seconds / 60
    regular_cap_minutes = config.shift_duration_minutes + config.overtime_threshold_minutes

    regular_minutes = min(active_minutes, regular_cap_minutes)
    overtime_minutes = max(active_minutes - regular_cap_minutes, 0)

    hourly_rate = float(config.hourly_rate)
    overtime_multiplier = float(config.overtime_multiplier)

    regular_earnings = (regular_minutes / 60) * hourly_rate if config.is_salary_enabled else 0.0
    overtime_earnings = (overtime_minutes / 60) * hourly_rate * overtime_multiplier if config.is_salary_enabled else 0.0

    return {
        "regular_minutes": round(regular_minutes, 2),
        "overtime_minutes": round(overtime_minutes, 2),
        "regular_earnings": round(regular_earnings, 2),
        "overtime_earnings": round(overtime_earnings, 2),
        "total_earnings": round(regular_earnings + overtime_earnings, 2),
        "currency": config.currency,
    }


def compute_daily_summary(employee, date, *, config=None, now=None):
    """Aggregates every session for ``employee`` on ``date`` (matched by
    ``login_at``'s own date — a session that spans midnight is
    attributed to the day it started on) into the single "Daily
    Attendance Record" shape Part 7 describes. Computed on read from the
    session/segment ledger, never a separately-maintained row that could
    drift out of sync — same "derived, never hand-edited" rule as
    ``compute_session_totals()``.
    """
    now = now or timezone.now()
    config = config or get_active_shift_configuration()

    sessions = list(
        AttendanceSession.active_objects.for_employee(employee).filter(login_at__date=date).order_by("login_at")
    )

    if not sessions:
        return None

    totals = {"session_seconds": 0, "active_working_seconds": 0, "break_seconds": 0, "idle_seconds": 0, "break_count": 0}
    for session in sessions:
        session_totals = compute_session_totals(session, now=now)
        for key in totals:
            totals[key] += session_totals[key]

    login_time = sessions[0].login_at
    still_open = any(s.logout_at is None for s in sessions)
    logout_time = None if still_open else max(s.logout_at for s in sessions)

    active_minutes = totals["active_working_seconds"] / 60
    shift_minutes = config.shift_duration_minutes
    overtime_minutes = max(active_minutes - shift_minutes - config.overtime_threshold_minutes, 0)
    short_minutes = max(shift_minutes - active_minutes, 0) if not still_open else 0

    if still_open:
        status = "In Progress"
    elif overtime_minutes > 0:
        status = "Overtime"
    elif short_minutes > 0:
        status = "Short Hours"
    else:
        status = "On Track"

    earnings = calculate_earnings(totals["active_working_seconds"], config=config)

    return {
        "employee_id": employee.id,
        "employee_name": f"{employee.first_name} {employee.last_name}".strip() or employee.email,
        "date": date,
        "login_time": login_time,
        "logout_time": logout_time,
        "session_seconds": totals["session_seconds"],
        "active_working_seconds": totals["active_working_seconds"],
        "break_seconds": totals["break_seconds"],
        "idle_seconds": totals["idle_seconds"],
        "number_of_breaks": totals["break_count"],
        "number_of_sessions": len(sessions),
        "status": status,
        "shift_minutes": shift_minutes,
        "overtime_minutes": round(overtime_minutes, 2),
        "short_minutes": round(short_minutes, 2),
        "earnings": earnings,
        "is_open": still_open,
    }


__all__ = [
    "get_active_shift_configuration",
    "start_session",
    "record_heartbeat",
    "start_break",
    "end_break",
    "end_session",
    "compute_session_totals",
    "compute_display_state",
    "calculate_earnings",
    "compute_daily_summary",
]
