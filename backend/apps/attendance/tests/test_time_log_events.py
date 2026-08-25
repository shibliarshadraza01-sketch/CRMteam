"""Regression tests for the two duplicate-attendance-event bugs found in
real database rows during the Phase 3 audit.

Both bugs made the Check In / Check Out UI report events that never
happened. They are covered here at the level the UI actually consumes —
the ``type`` sequence of ``build_time_logs()`` — because that is the
thing a user reads off the screen, and asserting on segment counts alone
would have let both bugs through.
"""
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.attendance.models import AttendanceSession, TimeSegment
from apps.attendance.services import (
    build_time_logs,
    end_break,
    end_session,
    start_break,
    start_session,
)

pytestmark = pytest.mark.django_db


def _log_types(employee):
    sessions = list(AttendanceSession.active_objects.for_employee(employee).order_by("login_at"))
    return [entry["type"] for entry in build_time_logs(sessions)]


def test_fresh_check_in_emits_only_check_in(employee):
    """A brand new arrival is ONE event. The reported bug was a spurious
    "Work resumed" rendered immediately after "Checked in", claiming a
    break that never happened.
    """
    start_session(employee)

    assert _log_types(employee) == ["CHECK_IN"]


def test_repeated_start_session_same_day_does_not_add_check_ins(employee):
    """Every mount of the frontend's attendance hook calls start_session.
    A page refresh is not an arrival.
    """
    first = start_session(employee)
    for _ in range(4):
        again = start_session(employee)
        assert again.pk == first.pk

    assert _log_types(employee) == ["CHECK_IN"]
    assert AttendanceSession.active_objects.for_employee(employee).count() == 1


def test_break_boundaries_are_one_event_each(employee):
    """THE GENERALIZED BUG. Going on a break used to emit "Work paused"
    AND "Break started" at one identical timestamp, and returning emitted
    "Break ended" AND "Work resumed" — four log lines for two real
    transitions. The full spec sequence must read cleanly.
    """
    session = start_session(employee)
    start_break(session)
    end_break(session)
    end_session(session)

    assert _log_types(employee) == ["CHECK_IN", "BREAK_START", "WORK_START", "CHECK_OUT"]


def test_no_duplicate_timestamps_anywhere_in_the_log(employee):
    """Structural guarantee behind the sequences above: no two log
    entries may share an instant, whatever the transitions were.
    """
    session = start_session(employee)
    start_break(session)
    end_break(session)
    start_break(session)
    end_break(session)
    end_session(session)

    logs = build_time_logs([session])
    instants = [entry["at"] for entry in logs]
    assert len(instants) == len(set(instants))


def test_idle_boundaries_are_one_event_each(employee):
    """Going idle and coming back are one event each, exactly as breaks
    are — the idle path built its segments through a different function
    and so needed its own coverage.
    """
    now = timezone.now()
    session = start_session(employee, now=now)
    # An idle stretch, shaped exactly as record_heartbeat() records one:
    # the open WORK segment closed, an IDLE segment for the gap, a new
    # WORK segment following it contiguously.
    opening = session.segments.active().order_by("started_at").first()
    idle_start = now + timedelta(minutes=1)
    idle_end = now + timedelta(minutes=30)
    opening.ended_at = idle_start
    opening.save(update_fields=["ended_at", "updated_at"])
    TimeSegment.objects.create(
        session=session,
        segment_type=TimeSegment.SegmentType.IDLE,
        started_at=idle_start,
        ended_at=idle_end,
    )
    TimeSegment.objects.create(
        session=session, segment_type=TimeSegment.SegmentType.WORK, started_at=idle_end
    )
    end_session(session, now=idle_end + timedelta(minutes=5))

    assert _log_types(employee) == ["CHECK_IN", "IDLE_START", "WORK_START", "CHECK_OUT"]


def test_full_spec_sequence_across_two_days(employee):
    """The exact sequence the spec asks to be verified: new day check-in
    -> check in again same day -> break -> resume -> checkout -> next day
    check-in. Each day must stand on its own with one arrival.
    """
    day_one = timezone.now()
    session = start_session(employee, now=day_one)
    start_session(employee, now=day_one + timedelta(minutes=1))
    start_break(session, now=day_one + timedelta(hours=1))
    end_break(session, now=day_one + timedelta(hours=1, minutes=30))
    end_session(session, now=day_one + timedelta(hours=8))

    day_two = day_one + timedelta(days=1)
    start_session(employee, now=day_two)

    assert _log_types(employee) == [
        "CHECK_IN",
        "BREAK_START",
        "WORK_START",
        "CHECK_OUT",
        "CHECK_IN",
    ]


def test_stale_overnight_session_is_closed_and_new_day_gets_its_own_check_in(employee):
    """Day-scoping must survive the changes above: an open session left
    over from yesterday is closed, today gets a genuine new arrival, and
    neither day gains a phantom event.
    """
    yesterday = timezone.now() - timedelta(days=1)
    stale = start_session(employee, now=yesterday)

    today_session = start_session(employee)

    stale.refresh_from_db()
    assert stale.logout_at is not None
    assert today_session.pk != stale.pk
    assert _log_types(employee) == ["CHECK_IN", "CHECK_OUT", "CHECK_IN"]


class _SqlRecorder:
    """Records every statement executed inside the ``with`` block."""

    def __init__(self):
        self.statements = []

    def __call__(self, execute, sql, params, many, context):
        self.statements.append(sql)
        return execute(sql, params, many, context)


def test_start_session_takes_a_row_lock_to_prevent_duplicate_sessions(employee):
    """CONCURRENCY REGRESSION. Two simultaneous arrivals for one employee
    both read "no open session" and both INSERT, leaving two open
    sessions milliseconds apart and two "Checked in" lines on the day's
    log. Real rows in this shape were found in the development database
    (two open sessions 3ms apart for one employee).

    A true parallel-transaction race cannot be staged inside pytest's
    single wrapping transaction, so this asserts the mechanism that
    prevents it: the employee row is locked FOR UPDATE before the
    check-then-create, which serializes concurrent callers.
    """
    recorder = _SqlRecorder()
    with connection.execute_wrapper(recorder):
        start_session(employee)

    assert any("FOR UPDATE" in sql.upper() for sql in recorder.statements), (
        "start_session must lock the employee row before deciding whether to "
        "create a session, otherwise concurrent calls duplicate it. "
        f"Statements seen: {recorder.statements}"
    )
