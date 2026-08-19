"""Serializers for the attendance/working-hours domain.

``AttendanceSessionSerializer``/``TimeSegmentSerializer`` mix in CP7's
``SoftDeleteTimeStampedSerializerMixin`` like every other domain
serializer in this project. The reporting shapes (``DailyAttendanceSerializer``,
``EarningsSerializer``) are plain ``Serializer`` subclasses, not
``ModelSerializer`` — ``services.compute_daily_summary()``/
``calculate_earnings()`` return plain dicts computed from the ledger,
never a model instance of their own (see those functions' own
docstrings for why: nothing here is stored redundantly).
"""
from rest_framework import serializers

from apps.core.serializers import SoftDeleteTimeStampedSerializerMixin

from .models import AttendanceSession, ShiftConfiguration, TimeSegment


class ShiftConfigurationSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = ShiftConfiguration
        fields = [
            "id", "shift_duration_minutes", "shift_start_time", "shift_end_time",
            "allowed_break_minutes", "idle_timeout_minutes", "overtime_threshold_minutes",
            "is_salary_enabled", "hourly_rate", "overtime_multiplier", "currency",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class TimeSegmentSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = TimeSegment
        fields = [
            "id", "session", "segment_type", "started_at", "ended_at",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = fields


class AttendanceSessionSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Read-only from the client's perspective — every state transition
    goes through a dedicated action (``start``/``heartbeat``/
    ``break-start``/``break-end``/``end``), never a plain PATCH, the
    same "no supported way to reach a new status through a plain PATCH"
    rule this project's own ``InvoiceSerializer`` already established.
    Computed fields (totals, display state) are added by the view via
    ``to_representation``-friendly extra keys — see ``views.py``'s
    ``_serialize_session()``.
    """

    class Meta:
        model = AttendanceSession
        fields = [
            "id", "employee", "login_at", "logout_at", "state", "last_heartbeat_at",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = fields


class EarningsSerializer(serializers.Serializer):
    regular_minutes = serializers.FloatField()
    overtime_minutes = serializers.FloatField()
    regular_earnings = serializers.FloatField()
    overtime_earnings = serializers.FloatField()
    total_earnings = serializers.FloatField()
    currency = serializers.CharField()


class TimeLogEntrySerializer(serializers.Serializer):
    """One discrete clock event from a day's attendance — see
    ``services.build_time_logs()``. Presentation-only: derived from the
    existing ``TimeSegment`` ledger, never stored separately.
    """

    at = serializers.DateTimeField()
    type = serializers.CharField()


class DailyAttendanceSerializer(serializers.Serializer):
    """One employee's attendance record for one day — the exact shape
    Part 7 of the spec describes, computed by
    ``services.compute_daily_summary()``.

    Staff-management pass added the Check In / Check Out presentation
    fields (``check_in_time``/``check_out_time``/``gross_seconds``/
    ``effective_seconds``/``shift_start_time``/``shift_end_time``/
    ``time_logs``/``employee_role``). The original field names
    (``login_time``/``logout_time``/``session_seconds``/
    ``active_working_seconds``) are all still emitted unchanged — the new
    names are aliases over the same values, so no existing consumer
    breaks.
    """

    employee_id = serializers.IntegerField()
    employee_name = serializers.CharField()
    employee_role = serializers.CharField(required=False, allow_null=True)
    date = serializers.DateField()
    login_time = serializers.DateTimeField(allow_null=True)
    logout_time = serializers.DateTimeField(allow_null=True)
    check_in_time = serializers.DateTimeField(allow_null=True, required=False)
    check_out_time = serializers.DateTimeField(allow_null=True, required=False)
    gross_seconds = serializers.IntegerField(required=False)
    effective_seconds = serializers.IntegerField(required=False)
    shift_start_time = serializers.TimeField(allow_null=True, required=False)
    shift_end_time = serializers.TimeField(allow_null=True, required=False)
    time_logs = TimeLogEntrySerializer(many=True, required=False)
    session_seconds = serializers.IntegerField()
    active_working_seconds = serializers.IntegerField()
    break_seconds = serializers.IntegerField()
    idle_seconds = serializers.IntegerField()
    number_of_breaks = serializers.IntegerField()
    number_of_sessions = serializers.IntegerField()
    status = serializers.CharField()
    shift_minutes = serializers.IntegerField()
    overtime_minutes = serializers.FloatField()
    short_minutes = serializers.FloatField()
    earnings = EarningsSerializer()
    is_open = serializers.BooleanField()


class CurrentSessionSerializer(serializers.Serializer):
    """``GET .../current/`` — the Employee Dashboard widget's one
    request: the open (or most recent) session, its live totals, real-
    time display state, and the shift policy it's being measured
    against, all in one payload so the frontend timer never has to
    stitch together multiple requests just to render itself.
    """

    session = AttendanceSessionSerializer(allow_null=True)
    display_state = serializers.CharField()
    totals = serializers.DictField()
    shift = ShiftConfigurationSerializer()
    earnings = EarningsSerializer()
