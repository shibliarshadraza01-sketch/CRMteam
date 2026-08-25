"""CP16: the reporting/dashboard domain's REST API.

Every viewset reuses CP10's ``_CrmModelViewSet`` (``apps.crm.views``)
directly across the app boundary — all four models here have a real or
delegating ``owner``, the same cross-app reuse CP12/CP14/CP15 already
established. No new ownership-scoping logic anywhere in this module.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.permissions import assert_object_accessible, is_super_admin
from apps.core.utils import stamp_audit_fields
from apps.crm.services import resolve_owner_for_create
from apps.crm.views import _CrmModelViewSet

from .filters import (
    DashboardFilterSet,
    DashboardWidgetFilterSet,
    ReportExecutionFilterSet,
    SavedReportFilterSet,
)
from .models import Dashboard, DashboardWidget, ReportExecution, SavedReport
from .serializers import (
    DashboardDetailSerializer,
    DashboardSerializer,
    DashboardWidgetSerializer,
    ReportExecutionSerializer,
    SavedReportSerializer,
)
from .services import add_widget, compute_company_dashboard_summary, execute_report, set_default_dashboard


class SavedReportViewSet(_CrmModelViewSet):
    """CRUD (via ``_CrmModelViewSet``) plus one custom action —
    ``execute`` — a thin wrapper around ``services.execute_report()``, so
    the actual computation dispatch lives in exactly one place, not
    duplicated here (the same "custom actions are thin wrappers around
    services" shape as CP11's ``OpportunityViewSet``).
    """

    base_manager = SavedReport.objects
    base_active_manager = SavedReport.active_objects
    serializer_class = SavedReportSerializer
    filterset_class = SavedReportFilterSet
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at", "report_type"]
    ordering = ["name"]

    def get_queryset(self):
        return super().get_queryset().select_related("owner")

    def perform_create(self, serializer):
        """Defaults ``owner`` to the requesting user when not explicitly
        supplied — the same rule ``TaskViewSet``/``EventViewSet`` (CP14)
        already apply.
        """
        super().perform_create(serializer)
        report = serializer.instance
        resolved_owner = resolve_owner_for_create(self.request.user, report.owner)
        if resolved_owner.pk != report.owner_id:
            report.owner = resolved_owner
            report.save(update_fields=["owner", "updated_at"])

    def get_throttles(self):
        # Rate-limited: execute() runs a real database aggregation query
        # on demand — see config/settings/base.py's "expensive_operation"
        # scope docstring. Every other action on this viewset (list/
        # create/retrieve/etc.) is unaffected.
        if self.action == "execute":
            self.throttle_scope = "expensive_operation"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    @extend_schema(request=None, responses={201: ReportExecutionSerializer})
    @action(detail=True, methods=["post"])
    def execute(self, request, *args, **kwargs):
        """``POST /saved-reports/<id>/execute/`` — runs this report now
        (``services.execute_report()``) and returns the resulting
        ``ReportExecution``, COMPLETED or FAILED.
        """
        report = self.get_object()
        execution = execute_report(report, executed_by=request.user)
        serializer = ReportExecutionSerializer(execution)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ReportExecutionViewSet(_CrmModelViewSet):
    """Read-only — ``http_method_names`` excludes every write verb, so
    there is no create/update/delete/restore/hard-delete route (DRF
    returns 405 for any of them), matching this model's own "written
    automatically by ``execute_report()``, never by a client" design —
    the same integrity-boundary pattern CP15's ``CommunicationLogViewSet``
    established.
    """

    base_manager = ReportExecution.objects
    base_active_manager = ReportExecution.active_objects
    serializer_class = ReportExecutionSerializer
    filterset_class = ReportExecutionFilterSet
    owner_field = "report__owner"
    http_method_names = ["get", "head", "options"]
    search_fields = ["report__name"]
    ordering_fields = ["created_at", "completed_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("report", "executed_by")


class DashboardViewSet(_CrmModelViewSet):
    base_manager = Dashboard.objects
    base_active_manager = Dashboard.active_objects
    serializer_class = DashboardSerializer
    filterset_class = DashboardFilterSet
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("owner")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("widgets")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DashboardDetailSerializer
        return DashboardSerializer

    def perform_create(self, serializer):
        """Defaults ``owner`` to the requesting user, same rule as
        ``SavedReportViewSet``. ``is_default`` is read-only on the
        serializer (see ``serializers.py``) — only reachable via the
        ``set-default`` action below, so the demote-then-promote
        invariant (``services.set_default_dashboard()``) can never be
        bypassed by a plain create/update payload.
        """
        super().perform_create(serializer)
        dashboard = serializer.instance
        resolved_owner = resolve_owner_for_create(self.request.user, dashboard.owner)
        if resolved_owner.pk != dashboard.owner_id:
            dashboard.owner = resolved_owner
            dashboard.save(update_fields=["owner", "updated_at"])

    @extend_schema(request=None, responses={200: DashboardSerializer})
    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, *args, **kwargs):
        """``POST /dashboards/<id>/set-default/`` — promotes this
        dashboard to its owner's default, demoting whichever dashboard
        previously held that spot (``services.set_default_dashboard()``).
        """
        dashboard = self.get_object()
        set_default_dashboard(dashboard)
        serializer = self.get_serializer(dashboard)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=False, methods=["get"], url_path="company-summary")
    def company_summary(self, request, *args, **kwargs):
        """``GET /dashboards/company-summary/`` — Reports/Dashboard audit
        pass: the Super Admin "This Month" + "All Time" company-wide
        figures (Total Leads, Total Converted Leads, Total Revenue,
        Pending Payments, Active Employees, Conversion Rate), computed
        entirely server-side by ``services.compute_company_dashboard_summary()``
        from the real Lead/Invoice/PaymentTransaction/User records — never
        frontend-aggregated. Super Admin only: this is a company-wide
        figure, not a Manager's team or an Employee's own scope (which
        already have their own scoped views elsewhere).
        """
        if not is_super_admin(request.user):
            return Response({"detail": "Super Admin only."}, status=status.HTTP_403_FORBIDDEN)
        return Response(compute_company_dashboard_summary())


class DashboardWidgetViewSet(_CrmModelViewSet):
    base_manager = DashboardWidget.objects
    base_active_manager = DashboardWidget.active_objects
    serializer_class = DashboardWidgetSerializer
    filterset_class = DashboardWidgetFilterSet
    owner_field = "dashboard__owner"
    search_fields = ["title"]
    ordering_fields = ["position", "created_at"]
    ordering = ["dashboard", "position"]

    def get_queryset(self):
        return super().get_queryset().select_related("dashboard", "dashboard__owner", "report")

    def perform_create(self, serializer):
        """Routes creation through ``services.add_widget()`` — real
        behavior: auto-assigns ``position`` when omitted, the same
        auto-ordering convenience CP12's ``QuoteItemViewSet``/
        ``InvoiceItemViewSet`` established for their own item models.
        """
        data = dict(serializer.validated_data)
        dashboard = data.pop("dashboard")
        report = data.pop("report")
        assert_object_accessible(self.request, dashboard)
        assert_object_accessible(self.request, report)
        widget_type = data.pop("widget_type")
        title = data.pop("title")
        position = data.pop("position", None)
        configuration = data.pop("configuration", None)

        widget = add_widget(
            dashboard, report, widget_type, title, position=position, configuration=configuration
        )
        stamp_audit_fields(widget, self.request.user, creating=True)
        widget.save()
        serializer.instance = widget
