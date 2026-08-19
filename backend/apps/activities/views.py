"""CP14: the activity layer's REST API.

Reuses CP10's ``_CrmModelViewSet`` (``apps.crm.views``) directly, exactly
like CP12's ``apps/sales/views.py`` already does — that base class has no
CRM-specific logic in its own implementation (HTTP-method restriction,
CP6's ``IsOwnerOrSuperAdmin``, the active-vs-unfiltered ``get_queryset()``
split), only its current location, and CP14's rules require reusing
existing infrastructure rather than redefining it a third time.

`Task`/`Event`/`ActivityLog` all have a real ownership-shaped field
(``owner`` or ``actor``), so ``_CrmModelViewSet``'s ``owner_field`` hook
covers them unchanged. `Reminder` does not — it delegates ownership to
whichever of `task`/`event` it belongs to (see ``models.py``), a shape
``scope_queryset_for_user()``'s single-field-path design can't express
directly (it can't follow "whichever of two mutually exclusive FKs is
set"). ``ReminderViewSet`` below overrides ``get_queryset()`` with a
Q-based equivalent of the exact same three-tier rule
(``scope_queryset_for_user()``'s own docstring) rather than duplicating it.
"""
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import assert_object_accessible, is_super_admin, user_has_role_at_least
from apps.accounts.models import User
from apps.core.utils import stamp_audit_fields
from apps.crm.services import resolve_owner_for_create
from apps.crm.views import _CrmModelViewSet

from .filters import ActivityLogFilterSet, EventFilterSet, ReminderFilterSet, TaskFilterSet
from .models import ActivityLog, Event, Reminder, Task
from .serializers import (
    ActivityLogSerializer,
    EventSerializer,
    ReminderDetailSerializer,
    ReminderSerializer,
    TaskSerializer,
)
from .services import (
    RECENT_ACTIVITY_DEFAULT_DAYS,
    RECENT_ACTIVITY_DEFAULT_LIMIT,
    cancel_task,
    complete_task,
    create_reminder,
    generate_occurrences,
    get_recent_activity,
    get_timeline,
    managed_user_ids,
    mark_reminder_sent,
    reassign_task,
    scope_queryset_for_user,
)


class TaskViewSet(_CrmModelViewSet):
    base_manager = Task.objects
    base_active_manager = Task.active_objects
    serializer_class = TaskSerializer
    filterset_class = TaskFilterSet
    search_fields = ["title", "description"]
    ordering_fields = ["due_date", "priority", "created_at", "status"]
    ordering = ["due_date"]

    def get_queryset(self):
        return super().get_queryset().select_related("owner", "assigned_to", "content_type")

    def perform_create(self, serializer):
        """Defaults ``owner`` to the requesting user when not explicitly
        supplied — the same rule ``LeadViewSet``/``OpportunityViewSet``
        already apply (CP10/CP11).
        """
        super().perform_create(serializer)
        task = serializer.instance
        resolved_owner = resolve_owner_for_create(self.request.user, task.owner)
        if resolved_owner.pk != task.owner_id:
            task.owner = resolved_owner
            task.save(update_fields=["owner", "updated_at"])

    def _task_response(self, task):
        serializer = self.get_serializer(task)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: TaskSerializer})
    @action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs):
        """``POST /tasks/<id>/complete/`` — sets ``status=COMPLETED`` and
        stamps ``completed_at`` (``services.complete_task()``); rejects an
        already-completed/cancelled task.
        """
        task = self.get_object()
        try:
            complete_task(task)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._task_response(task)

    @extend_schema(request=None, responses={200: TaskSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs):
        """``POST /tasks/<id>/cancel/`` (``services.cancel_task()``)."""
        task = self.get_object()
        try:
            cancel_task(task)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._task_response(task)

    @extend_schema(request=None, responses={200: TaskSerializer})
    @action(detail=True, methods=["post"])
    def reassign(self, request, *args, **kwargs):
        """``POST /tasks/<id>/reassign/`` — ``{"assigned_to": <user id>}``
        (``services.reassign_task()``); omitting ``assigned_to`` unassigns.
        """
        task = self.get_object()
        user_id = request.data.get("assigned_to")
        user = get_object_or_404(User, pk=user_id) if user_id else None
        reassign_task(task, user)
        return self._task_response(task)


class EventViewSet(_CrmModelViewSet):
    base_manager = Event.objects
    base_active_manager = Event.active_objects
    serializer_class = EventSerializer
    filterset_class = EventFilterSet
    search_fields = ["title", "description", "location"]
    ordering_fields = ["start_at", "created_at"]
    ordering = ["start_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("owner", "content_type")

    def perform_create(self, serializer):
        """See ``TaskViewSet.perform_create()`` — identical reasoning."""
        super().perform_create(serializer)
        event = serializer.instance
        resolved_owner = resolve_owner_for_create(self.request.user, event.owner)
        if resolved_owner.pk != event.owner_id:
            event.owner = resolved_owner
            event.save(update_fields=["owner", "updated_at"])

    @extend_schema(
        request=None,
        responses={200: None},
        parameters=[OpenApiParameter("limit", int, description="Max occurrences to compute (default 52).")],
    )
    @action(detail=True, methods=["get"])
    def occurrences(self, request, *args, **kwargs):
        """``GET /events/<id>/occurrences/`` — computes this event's basic
        recurrence occurrence datetimes (``services.generate_occurrences()``)
        without persisting anything.
        """
        event = self.get_object()
        limit = int(request.query_params.get("limit", 52))
        occurrences = generate_occurrences(event, limit=limit)
        return Response({"occurrences": [dt.isoformat() for dt in occurrences]})


class ActivityLogViewSet(_CrmModelViewSet):
    base_manager = ActivityLog.objects
    base_active_manager = ActivityLog.active_objects
    serializer_class = ActivityLogSerializer
    filterset_class = ActivityLogFilterSet
    owner_field = "actor"
    search_fields = ["description"]
    ordering_fields = ["occurred_at", "created_at"]
    ordering = ["-occurred_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("actor", "content_type")

    def perform_create(self, serializer):
        """Defaults ``actor`` to the requesting user when not explicitly
        supplied — same "default to the requester" rule as
        ``TaskViewSet``/``EventViewSet``, applied to this model's ``actor``
        field instead of ``owner``.
        """
        super().perform_create(serializer)
        log = serializer.instance
        if log.actor_id is None:
            log.actor = self.request.user
            log.save(update_fields=["actor", "updated_at"])


class ReminderViewSet(_CrmModelViewSet):
    base_manager = Reminder.objects
    base_active_manager = Reminder.active_objects
    serializer_class = ReminderSerializer
    filterset_class = ReminderFilterSet
    search_fields = ["message"]
    ordering_fields = ["remind_at"]
    ordering = ["remind_at"]

    def get_queryset(self):
        """Cannot reuse ``scope_queryset_for_user()`` unchanged — see this
        module's docstring. Applies the identical three-tier rule
        (Super Admin: everything; Manager: their team's task/event owners;
        Employee: their own task/event) via ``Q(task__owner=...) |
        Q(event__owner=...)`` instead of a single ``owner_field`` path.
        """
        base_manager = self.base_active_manager if self.action == "list" else self.base_manager
        queryset = base_manager.all().select_related("task", "task__owner", "event", "event__owner")

        user = self.request.user
        if user is None or not getattr(user, "is_authenticated", False):
            return queryset.none()
        if is_super_admin(user):
            return queryset
        if user_has_role_at_least(user, User.Role.MANAGER):
            ids = managed_user_ids(user)
            return queryset.filter(Q(task__owner_id__in=ids) | Q(event__owner_id__in=ids))
        return queryset.filter(Q(task__owner=user) | Q(event__owner=user))

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ReminderDetailSerializer
        return ReminderSerializer

    def perform_create(self, serializer):
        """Routes creation through ``services.create_reminder()`` — real
        behavior: the "exactly one of task/event" guard (also enforced by
        the serializer and the DB constraint — same three-layer pattern as
        CP13's `PriceBookEntry`).
        """
        data = dict(serializer.validated_data)
        task = data.get("task")
        event = data.get("event")
        if task is not None:
            assert_object_accessible(self.request, task)
        if event is not None:
            assert_object_accessible(self.request, event)
        reminder = create_reminder(
            task=task, event=event, remind_at=data["remind_at"], message=data.get("message", "")
        )
        stamp_audit_fields(reminder, self.request.user, creating=True)
        reminder.save()
        serializer.instance = reminder

    @extend_schema(request=None, responses={200: ReminderSerializer})
    @action(detail=True, methods=["post"], url_path="mark-sent")
    def mark_sent(self, request, *args, **kwargs):
        """``POST /reminders/<id>/mark-sent/`` (``services.mark_reminder_sent()``)."""
        reminder = self.get_object()
        mark_reminder_sent(reminder)
        serializer = self.get_serializer(reminder)
        return Response(serializer.data, status=status.HTTP_200_OK)


class TimelineView(APIView):
    """``GET /api/v1/activities/timeline/?content_type=<app_label.model>&object_id=<id>``

    Returns the merged, chronologically-ordered `Task`/`Event`/`ActivityLog`
    timeline for one CRM entity (``services.get_timeline()``), scoped to
    what the requesting user is allowed to see via the same ownership rule
    every other endpoint in this app applies.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("content_type", str, required=True, description="e.g. 'crm.customer', 'sales.invoice'."),
            OpenApiParameter("object_id", int, required=True),
        ],
        responses={200: None},
    )
    def get(self, request, *args, **kwargs):
        from django.contrib.contenttypes.models import ContentType

        raw_content_type = request.query_params.get("content_type", "")
        object_id = request.query_params.get("object_id")
        if not raw_content_type or not object_id:
            return Response(
                {"detail": "Both content_type and object_id query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            app_label, model = raw_content_type.split(".")
            content_type = ContentType.objects.get(app_label=app_label, model=model)
        except (ValueError, ContentType.DoesNotExist):
            return Response({"detail": "Unknown content_type."}, status=status.HTTP_400_BAD_REQUEST)

        entity = content_type.get_object_for_this_type(pk=object_id)
        timeline = get_timeline(entity, user=request.user)

        return Response(
            [
                {
                    "kind": entry["kind"],
                    "timestamp": entry["timestamp"],
                    "id": entry["object"].pk,
                    "summary": str(entry["object"]),
                }
                for entry in timeline
            ]
        )


class RecentActivityView(APIView):
    """``GET /api/v1/activities/recent/?limit=&days=`` — the Recent
    Activities panel's data, built from REAL CRM state (leads converted/
    assigned, new customers, payments received/overdue, follow-ups
    scheduled, interactions logged, reminders generated, check-ins/outs,
    and — for a Super Admin — staff accounts created).

    Read-only and role-scoped by ``services.get_recent_activity()``, which
    applies the same ``scope_queryset_for_user()`` boundary as every list
    endpoint: Super Admin org-wide, Manager their own team, Employee their
    own records only. No new model backs this — see that function's
    docstring for why.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter("limit", int, required=False, description="Max entries (default 25, max 100)."),
            OpenApiParameter("days", int, required=False, description="Look-back window in days (default 7, max 90)."),
        ],
        responses={200: None},
    )
    def get(self, request, *args, **kwargs):
        def _bounded(name, default, maximum):
            raw = request.query_params.get(name)
            if raw is None:
                return default
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return default
            return max(1, min(value, maximum))

        entries = get_recent_activity(
            request.user,
            limit=_bounded("limit", RECENT_ACTIVITY_DEFAULT_LIMIT, 100),
            days=_bounded("days", RECENT_ACTIVITY_DEFAULT_DAYS, 90),
        )
        return Response(entries, status=status.HTTP_200_OK)
