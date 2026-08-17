"""Tests for apps/attendance/services.py — the sole place session state
transitions, idle detection, and payroll-relevant totals are computed.
"""
from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.attendance.models import AttendanceSession, TimeSegment
from apps.attendance.services import (
    calculate_earnings,
    compute_daily_summary,
    compute_display_state,
    compute_session_totals,
    end_break,
    end_session,
    get_active_shift_configuration,
    record_heartbeat,
    start_break,
    start_session,
)


@pytest.mark.django_db
def test_start_session_creates_open_work_segment(employee):
    now = timezone.now()
    session = start_session(employee, now=now)

    assert session.state == AttendanceSession.State.WORKING
    assert session.logout_at is None
    segments = list(session.segments.all())
    assert len(segments) == 1
    assert segments[0].segment_type == TimeSegment.SegmentType.WORK
    assert segments[0].ended_at is None


@pytest.mark.django_db
def test_start_session_closes_stale_open_session_for_same_employee(employee):
    t0 = timezone.now()
    first = start_session(employee, now=t0)

    second = start_session(employee, now=t0 + timedelta(hours=1))

    first.refresh_from_db()
    assert first.logout_at == t0 + timedelta(hours=1)
    assert first.state == AttendanceSession.State.OFFLINE
    assert second.logout_at is None
    assert AttendanceSession.active_objects.for_employee(employee).open().count() == 1


@pytest.mark.django_db
def test_end_session_is_idempotent(employee):
    t0 = timezone.now()
    session = start_session(employee, now=t0)

    end_session(session, now=t0 + timedelta(hours=8))
    session.refresh_from_db()
    first_logout = session.logout_at

    end_session(session, now=t0 + timedelta(hours=10))  # duplicate/retried logout
    session.refresh_from_db()

    assert session.logout_at == first_logout
    assert session.state == AttendanceSession.State.OFFLINE


@pytest.mark.django_db
def test_record_heartbeat_within_threshold_does_not_split_segment(employee, shift_config):
    t0 = timezone.now()
    session = start_session(employee, now=t0)

    record_heartbeat(session, now=t0 + timedelta(minutes=2))

    assert session.segments.count() == 1
    segment = session.segments.first()
    assert segment.segment_type == TimeSegment.SegmentType.WORK
    assert segment.ended_at is None


@pytest.mark.django_db
def test_record_heartbeat_gap_beyond_idle_threshold_creates_idle_segment(employee, shift_config):
    t0 = timezone.now()
    session = start_session(employee, now=t0)

    # No heartbeat for 12 minutes > 5 minute idle_timeout_minutes.
    gap_end = t0 + timedelta(minutes=12)
    record_heartbeat(session, now=gap_end)

    segments = list(session.segments.order_by("started_at"))
    assert [s.segment_type for s in segments] == [
        TimeSegment.SegmentType.WORK,
        TimeSegment.SegmentType.IDLE,
        TimeSegment.SegmentType.WORK,
    ]
    work1, idle, work2 = segments
    assert work1.ended_at == t0  # closed at the LAST KNOWN heartbeat, not "now"
    assert idle.started_at == t0
    assert idle.ended_at == gap_end
    assert work2.started_at == gap_end
    assert work2.ended_at is None


@pytest.mark.django_db
def test_idle_gap_is_excluded_from_active_working_time(employee, shift_config):
    t0 = timezone.now()
    session = start_session(employee, now=t0)

    idle_start_heartbeat = t0 + timedelta(minutes=2)
    record_heartbeat(session, now=idle_start_heartbeat)  # still within threshold

    gap_end = idle_start_heartbeat + timedelta(minutes=20)  # goes idle for 20 min
    record_heartbeat(session, now=gap_end)

    logout_time = gap_end + timedelta(minutes=10)
    end_session(session, now=logout_time)

    totals = compute_session_totals(session, now=logout_time)
    # Work: 0-2min, then 20-30min (after the idle gap) = 12 minutes total.
    assert totals["active_working_seconds"] == pytest.approx(12 * 60, abs=1)
    assert totals["idle_seconds"] == pytest.approx(20 * 60, abs=1)
    # session_seconds is the ONLY place login/logout subtraction happens.
    assert totals["session_seconds"] == int((logout_time - t0).total_seconds())
    assert totals["active_working_seconds"] < totals["session_seconds"]


@pytest.mark.django_db
def test_start_break_pauses_work_and_end_break_resumes(employee, shift_config):
    t0 = timezone.now()
    session = start_session(employee, now=t0)

    break_start = t0 + timedelta(hours=2)
    start_break(session, now=break_start)
    session.refresh_from_db()
    assert session.state == AttendanceSession.State.ON_BREAK

    break_end = break_start + timedelta(minutes=30)
    end_break(session, now=break_end)
    session.refresh_from_db()
    assert session.state == AttendanceSession.State.WORKING

    logout_time = break_end + timedelta(hours=1)
    end_session(session, now=logout_time)

    totals = compute_session_totals(session, now=logout_time)
    assert totals["break_seconds"] == 30 * 60
    assert totals["break_count"] == 1
    # 2h before break + 1h after break = 3h of work; break excluded.
    assert totals["active_working_seconds"] == 3 * 60 * 60


@pytest.mark.django_db
def test_start_break_rejects_when_not_working(employee):
    session = start_session(employee)
    start_break(session)

    with pytest.raises(ValueError):
        start_break(session)  # already on break


@pytest.mark.django_db
def test_end_break_rejects_when_not_on_break(employee):
    session = start_session(employee)

    with pytest.raises(ValueError):
        end_break(session)  # never started a break


@pytest.mark.django_db
def test_compute_display_state_offline_when_no_session():
    assert compute_display_state(None) == AttendanceSession.State.OFFLINE


@pytest.mark.django_db
def test_compute_display_state_offline_after_logout(employee):
    session = start_session(employee)
    end_session(session)
    assert compute_display_state(session) == AttendanceSession.State.OFFLINE


@pytest.mark.django_db
def test_compute_display_state_on_break(employee):
    session = start_session(employee)
    start_break(session)
    assert compute_display_state(session) == AttendanceSession.State.ON_BREAK


@pytest.mark.django_db
def test_compute_display_state_idle_when_heartbeat_stale(employee, shift_config):
    t0 = timezone.now()
    session = start_session(employee, now=t0)
    later = t0 + timedelta(minutes=10)  # beyond 5 min idle_timeout_minutes
    assert compute_display_state(session, config=shift_config, now=later) == "IDLE"


@pytest.mark.django_db
def test_compute_display_state_working_when_heartbeat_fresh(employee, shift_config):
    t0 = timezone.now()
    session = start_session(employee, now=t0)
    soon = t0 + timedelta(minutes=1)
    assert compute_display_state(session, config=shift_config, now=soon) == AttendanceSession.State.WORKING


@pytest.mark.django_db
def test_calculate_earnings_regular_only(shift_config):
    # 4 hours of active work, well under the 9h shift cap.
    earnings = calculate_earnings(4 * 3600, config=shift_config)
    assert earnings["overtime_minutes"] == 0
    assert earnings["regular_minutes"] == pytest.approx(240)
    assert earnings["regular_earnings"] == pytest.approx(4 * 20)
    assert earnings["total_earnings"] == pytest.approx(4 * 20)


@pytest.mark.django_db
def test_calculate_earnings_includes_overtime_at_multiplier(shift_config):
    # 10 hours active: 9h regular (shift cap) + 1h overtime at 1.5x.
    earnings = calculate_earnings(10 * 3600, config=shift_config)
    assert earnings["regular_minutes"] == pytest.approx(540)
    assert earnings["overtime_minutes"] == pytest.approx(60)
    assert earnings["regular_earnings"] == pytest.approx(9 * 20)
    assert earnings["overtime_earnings"] == pytest.approx(1 * 20 * 1.5)
    assert earnings["total_earnings"] == pytest.approx(9 * 20 + 1 * 20 * 1.5)


@pytest.mark.django_db
def test_calculate_earnings_zero_when_salary_disabled(employee):
    from apps.attendance.models import ShiftConfiguration

    config = ShiftConfiguration.objects.create(is_salary_enabled=False, hourly_rate=50)
    earnings = calculate_earnings(8 * 3600, config=config)
    assert earnings["regular_earnings"] == 0.0
    assert earnings["overtime_earnings"] == 0.0
    assert earnings["total_earnings"] == 0.0


@pytest.mark.django_db
def test_compute_daily_summary_returns_none_without_sessions(employee):
    assert compute_daily_summary(employee, date.today()) is None


@pytest.mark.django_db
def test_compute_daily_summary_short_hours_status(employee, shift_config):
    today = timezone.localdate()
    login = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
    session = start_session(employee, now=login)

    break_start = login + timedelta(hours=4)
    start_break(session, now=break_start)
    break_end = break_start + timedelta(hours=1, minutes=25)
    end_break(session, now=break_end)

    logout = login + timedelta(hours=9, minutes=30)  # 9h30m session, 1h25m break
    end_session(session, now=logout)

    summary = compute_daily_summary(employee, today, config=shift_config)

    assert summary["employee_id"] == employee.id
    assert summary["number_of_sessions"] == 1
    assert summary["number_of_breaks"] == 1
    assert summary["is_open"] is False
    assert summary["break_seconds"] == pytest.approx(85 * 60, abs=1)
    # Active = 9h30m session - 1h25m break = 8h05m.
    assert summary["active_working_seconds"] == pytest.approx((8 * 60 + 5) * 60, abs=1)
    assert summary["status"] == "Short Hours"
    assert summary["short_minutes"] == pytest.approx(55, abs=1)


@pytest.mark.django_db
def test_compute_daily_summary_in_progress_when_session_still_open(employee, shift_config):
    today = timezone.localdate()
    login = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
    start_session(employee, now=login)

    summary = compute_daily_summary(employee, today, config=shift_config, now=login + timedelta(hours=2))
    assert summary["is_open"] is True
    assert summary["status"] == "In Progress"
    assert summary["logout_time"] is None


@pytest.mark.django_db
def test_get_active_shift_configuration_auto_creates_default_when_none_exists():
    from apps.attendance.models import ShiftConfiguration

    assert ShiftConfiguration.active_objects.count() == 0
    config = get_active_shift_configuration()
    assert config.shift_duration_minutes == 540
    assert ShiftConfiguration.active_objects.count() == 1


@pytest.mark.django_db
def test_get_active_shift_configuration_returns_newest_existing_row(shift_config):
    from apps.attendance.models import ShiftConfiguration

    newer = ShiftConfiguration.objects.create(shift_duration_minutes=480)
    assert get_active_shift_configuration().id == newer.id
