"""The attendance/working-hours REST API.

``ShiftConfigurationViewSet`` — Super Admin configures, everyone else
reads (``ReadOnlyOrSuperAdmin``, same class ``apps.organization`` already
uses for an identical "everyone reads company policy, only Super Admin
edits it" shape).

``AttendanceSessionViewSet`` — read-only list/retrieve (own sessions, or
a Manager's team's, or Super Admin's company-wide, via the same
``scope_queryset_for_user()`` every other domain in this project uses)
plus the real state-machine actions (``start``/``heartbeat``/
``break-start``/``break-end``/``end``/``current``) and the reporting
actions (``daily-summary``/``team-status``/``company-report``).
"""
import datetime

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.models import User
from apps.accounts.permissions import is_super_admin, user_has_role_at_least
from apps.core.utils import stamp_audit_fields
from apps.core.views import SoftDeleteAuditModelViewSetMixin
from apps.crm.services import managed_user_ids, scope_queryset_for_user

from .filters import AttendanceSessionFilterSet
from .models import AttendanceSession
from .permissions import IsOwnerOrSuperAdmin, ReadOnlyOrSuperAdmin
from .serializers import (
    AttendanceSessionSerializer,
    CurrentSessionSerializer,
    DailyAttendanceSerializer,
    ShiftConfigurationSerializer,
)
from .services import (
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
from .models import ShiftConfiguration


class ShiftConfigurationViewSet(SoftDeleteAuditModelViewSetMixin, viewsets.ModelViewSet):
    """Super Admin configures the company's one shift policy; everyone
    authenticated can read it (an employee's dashboard needs to know
    the shift length to show "Remaining: 00:55"). ``current`` returns
    the effective policy directly (auto-creating the default row on
    first access — see ``services.get_active_shift_configuration()``),
    saving the frontend from listing + picking the newest row itself.
    """

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated, ReadOnlyOrSuperAdmin]
    base_manager = ShiftConfiguration.objects
    base_active_manager = ShiftConfiguration.active_objects
    serializer_class = ShiftConfigurationSerializer
    ordering = ["-created_at"]

    def get_queryset(self):
        base_manager = self.base_active_manager if self.action == "list" else self.base_manager
        return base_manager.all()

    @extend_schema(request=None, responses={200: ShiftConfigurationSerializer})
    @action(detail=False, methods=["get"])
    def current(self, request, *args, **kwargs):
        config = get_active_shift_configuration()
        return Response(ShiftConfigurationSerializer(config).data)


def _serialize_current(session, *, requesting_user_can_see_earnings=True):
    config = get_active_shift_configuration()
    now = timezone.now()
    totals = compute_session_totals(session, now=now) if session else {
        "session_seconds": 0, "active_working_seconds": 0, "break_seconds": 0, "idle_seconds": 0, "break_count": 0,
    }
    display_state = compute_display_state(session, config=config, now=now)
    earnings = calculate_earnings(totals["active_working_seconds"], config=config) if requesting_user_can_see_earnings else {
        "regular_minutes": 0, "overtime_minutes": 0, "regular_earnings": 0, "overtime_earnings": 0,
        "total_earnings": 0, "currency": config.currency,
    }
    payload = {
        "session": session,
        "display_state": display_state,
        "totals": totals,
        "shift": config,
        "earnings": earnings,
    }
    return CurrentSessionSerializer(payload).data


class AttendanceSessionViewSet(
    SoftDeleteAuditModelViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """List/retrieve only from the client's perspective — every write
    happens through one of the actions below, never a plain create/
    update/delete (there is no supported way to fabricate or edit an
    attendance record directly, the same integrity boundary this
    project already applies to system-written records like
    ``ReportExecution``/``AuditLog``).
    """

    http_method_names = ["get", "post", "head", "options"]
    permission_classes = [IsAuthenticated, IsOwnerOrSuperAdmin]
    base_manager = AttendanceSession.objects
    base_active_manager = AttendanceSession.active_objects
    serializer_class = AttendanceSessionSerializer
    filterset_class = AttendanceSessionFilterSet
    owner_field = "employee"
    ordering_fields = ["login_at", "logout_at"]
    ordering = ["-login_at"]

    def get_queryset(self):
        queryset = self.base_active_manager.all().select_related("employee")
        return scope_queryset_for_user(queryset, self.request.user, owner_field=self.owner_field)

    def _current_open_session(self, employee):
        return AttendanceSession.active_objects.for_employee(employee).open().order_by("-login_at").first()

    @extend_schema(request=None, responses={201: AttendanceSessionSerializer})
    @action(detail=False, methods=["post"])
    def start(self, request, *args, **kwargs):
        """``POST .../sessions/start/`` — called by the frontend right
        after a successful login (never by the login view itself; auth
        is deliberately untouched — see this app's own module docstring).
        """
        session = start_session(request.user)
        stamp_audit_fields(session, request.user, creating=True)
        session.save()
        return Response(_serialize_current(session), status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: CurrentSessionSerializer})
    @action(detail=False, methods=["post"])
    def heartbeat(self, request, *args, **kwargs):
        """``POST .../sessions/heartbeat/`` — see ``services.record_heartbeat()``'s
        own docstring for the idle/sleep/tab-away detection this single
        endpoint drives. 404 (not 400) if there is no open session — the
        frontend should always call ``start`` first; a heartbeat with no
        session to attach to means the client's own state is stale
        (e.g. this tab never actually registered a login).
        """
        session = self._current_open_session(request.user)
        if session is None:
            return Response({"detail": "No active attendance session."}, status=status.HTTP_404_NOT_FOUND)
        record_heartbeat(session)
        return Response(_serialize_current(session))

    @extend_schema(request=None, responses={200: CurrentSessionSerializer, 400: dict})
    @action(detail=False, methods=["post"], url_path="break-start")
    def break_start(self, request, *args, **kwargs):
        session = self._current_open_session(request.user)
        if session is None:
            return Response({"detail": "No active attendance session."}, status=status.HTTP_404_NOT_FOUND)
        try:
            start_break(session)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_serialize_current(session))

    @extend_schema(request=None, responses={200: CurrentSessionSerializer, 400: dict})
    @action(detail=False, methods=["post"], url_path="break-end")
    def break_end(self, request, *args, **kwargs):
        session = self._current_open_session(request.user)
        if session is None:
            return Response({"detail": "No active attendance session."}, status=status.HTTP_404_NOT_FOUND)
        try:
            end_break(session)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_serialize_current(session))

    @extend_schema(request=None, responses={200: CurrentSessionSerializer})
    @action(detail=False, methods=["post"])
    def end(self, request, *args, **kwargs):
        """``POST .../sessions/end/`` — called by the frontend as part of
        its own Logout handler, alongside (not instead of) the real
        ``apps.accounts`` logout call. Idempotent (see
        ``services.end_session()``): safe to call even if no session is
        open (returns a null-session payload rather than a 404 — a
        logout should never fail just because attendance tracking
        already considered the employee offline).
        """
        session = self._current_open_session(request.user)
        if session is not None:
            end_session(session)
        return Response(_serialize_current(session))

    @extend_schema(request=None, responses={200: CurrentSessionSerializer})
    @action(detail=False, methods=["get"])
    def current(self, request, *args, **kwargs):
        """``GET .../sessions/current/`` — the Employee Dashboard
        widget's one request (Part 10).
        """
        session = self._current_open_session(request.user)
        return Response(_serialize_current(session))

    def get_throttles(self):
        # Heartbeats fire every ~20-30s per active employee — the
        # default DRF rate would be far too tight; give this one action
        # a much higher scope instead of leaving it unthrottled.
        if self.action == "heartbeat":
            self.throttle_scope = "attendance_heartbeat"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    @extend_schema(request=None, responses={200: DailyAttendanceSerializer})
    @action(detail=False, methods=["get"], url_path="daily-summary")
    def daily_summary(self, request, *args, **kwargs):
        """``GET .../sessions/daily-summary/?employee_id=&date=`` — an
        employee's own record by default; a Manager may request any
        employee in their own team (``managed_user_ids()`` — the exact
        boundary already enforced everywhere else in this project);
        Super Admin may request anyone. Returns 404 (not 403) for a
        disallowed ``employee_id`` — consistent with every other
        cross-user access check in this project, which never confirms
        or denies that a given id exists for someone outside the
        requester's reach.
        """
        employee_id = request.query_params.get("employee_id")
        date_str = request.query_params.get("date")
        target_date = datetime.date.fromisoformat(date_str) if date_str else timezone.localdate()

        if employee_id and str(employee_id) != str(request.user.pk):
            if is_super_admin(request.user):
                employee = User.objects.filter(pk=employee_id).first()
            elif user_has_role_at_least(request.user, User.Role.MANAGER) and int(employee_id) in managed_user_ids(request.user):
                employee = User.objects.filter(pk=employee_id).first()
            else:
                employee = None
            if employee is None:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            employee = request.user

        summary = compute_daily_summary(employee, target_date)
        if summary is None:
            config = get_active_shift_configuration()
            return Response(
                {
                    "employee_id": employee.id,
                    "employee_name": f"{employee.first_name} {employee.last_name}".strip() or employee.email,
                    "employee_role": employee.role,
                    "date": target_date, "login_time": None, "logout_time": None,
                    # Staff-management pass: the Check In / Check Out aliases
                    # are present even on a no-record day, so a UI never has
                    # to branch on whether the employee worked.
                    "check_in_time": None, "check_out_time": None,
                    "gross_seconds": 0, "effective_seconds": 0,
                    "shift_start_time": config.shift_start_time,
                    "shift_end_time": config.shift_end_time,
                    "time_logs": [],
                    "session_seconds": 0, "active_working_seconds": 0, "break_seconds": 0, "idle_seconds": 0,
                    "number_of_breaks": 0, "number_of_sessions": 0, "status": "No Record",
                    "shift_minutes": config.shift_duration_minutes,
                    "overtime_minutes": 0, "short_minutes": 0, "is_open": False,
                    "earnings": {"regular_minutes": 0, "overtime_minutes": 0, "regular_earnings": 0, "overtime_earnings": 0, "total_earnings": 0, "currency": config.currency},
                }
            )
        return Response(DailyAttendanceSerializer(summary).data)

    @extend_schema(request=None, responses={200: DailyAttendanceSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="team-status")
    def team_status(self, request, *args, **kwargs):
        """``GET .../sessions/team-status/`` — Manager's (or Super
        Admin's) view of today's attendance for everyone they manage —
        Part 11. A plain Employee gets an empty list (``managed_user_ids()``
        for an Employee is just themselves, and this endpoint's whole
        point is "other people's status").
        """
        if not user_has_role_at_least(request.user, User.Role.MANAGER):
            return Response([])
        target_date_str = request.query_params.get("date")
        target_date = datetime.date.fromisoformat(target_date_str) if target_date_str else timezone.localdate()

        if is_super_admin(request.user):
            employees = User.objects.filter(is_active=True)
        else:
            employees = User.objects.filter(pk__in=managed_user_ids(request.user), is_active=True).exclude(pk=request.user.pk)

        results = []
        for employee in employees:
            summary = compute_daily_summary(employee, target_date)
            if summary is None:
                continue
            results.append(summary)
        return Response(DailyAttendanceSerializer(results, many=True).data)

    @extend_schema(request=None, responses={200: DailyAttendanceSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="company-report")
    def company_report(self, request, *args, **kwargs):
        """``GET .../sessions/company-report/?date_from=&date_to=`` —
        Super Admin only (Part 12). Bounded to a max 31-day window per
        request — a company-wide, day-by-day report over an unbounded
        range would mean an unbounded number of ``compute_daily_summary()``
        calls (each its own aggregate query) in one request; 31 days is
        generous for "daily/weekly/monthly" while still being a real
        limit, not unlimited computation from a single request.
        """
        if not is_super_admin(request.user):
            return Response({"detail": "Super Admin only."}, status=status.HTTP_403_FORBIDDEN)

        date_from_str = request.query_params.get("date_from")
        date_to_str = request.query_params.get("date_to")
        today = timezone.localdate()
        date_from = datetime.date.fromisoformat(date_from_str) if date_from_str else today
        date_to = datetime.date.fromisoformat(date_to_str) if date_to_str else today
        if (date_to - date_from).days > 31:
            return Response({"detail": "date range cannot exceed 31 days."}, status=status.HTTP_400_BAD_REQUEST)

        employees = list(User.objects.filter(is_active=True))
        results = []
        current = date_from
        while current <= date_to:
            for employee in employees:
                summary = compute_daily_summary(employee, current)
                if summary is not None:
                    results.append(summary)
            current += datetime.timedelta(days=1)
        return Response(DailyAttendanceSerializer(results, many=True).data)
