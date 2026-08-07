"""CP16: reporting and dashboard infrastructure.

    SavedReport --< ReportExecution
    Dashboard --< DashboardWidget >-- SavedReport

Every model inherits `apps.core.models.SoftDeleteTimeStampedModel` (CP7),
exactly like every CP9+ domain model.

`SavedReport`/`Dashboard` both have a real `owner` FK (CP10's
ownership-scoping model applies directly, same as every per-user record
since CP9). `ReportExecution`/`DashboardWidget` have no owner of their
own — both delegate via an `owner` PROPERTY to the record they belong to
(`report.owner`/`dashboard.owner` respectively), the same pattern CP9's
`ContactPerson.owner`/`Address.owner` established and every checkpoint
since has reused for a model that is conceptually "part of" a parent
record rather than independently owned.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteQuerySet, SoftDeleteTimeStampedModel

# --------------------------------------------------------------------------
# SavedReport
# --------------------------------------------------------------------------


class SavedReportQuerySet(SoftDeleteQuerySet):
    def active(self):
        return super().active().filter(is_active=True)

    def by_owner(self, user):
        return self.filter(owner=user)


class SavedReportManager(models.Manager.from_queryset(SavedReportQuerySet)):
    """``SavedReport.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveSavedReportManager(SavedReportManager):
    def get_queryset(self):
        return super().get_queryset().active()


class SavedReport(SoftDeleteTimeStampedModel):
    """A saved, re-runnable report DEFINITION — what to compute
    (`report_type`) and how to narrow it (`filters`), not the computed
    result itself (see `ReportExecution`, below, for that).
    """

    class ReportType(models.TextChoices):
        PRODUCTIVITY = "PRODUCTIVITY", _("Productivity")
        LEAD_CONVERSION = "LEAD_CONVERSION", _("Lead Conversion")
        SALES_PIPELINE = "SALES_PIPELINE", _("Sales Pipeline")
        CUSTOMER_ACTIVITY = "CUSTOMER_ACTIVITY", _("Customer Activity")
        CUSTOM = "CUSTOM", _("Custom")

    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")
    report_type = models.CharField(
        _("report type"), max_length=20, choices=ReportType.choices, db_index=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_reports",
    )
    filters = models.JSONField(
        _("filters"), default=dict, blank=True,
        help_text=_("Parameters narrowing this report's computation — e.g. a date range or an owner_id — interpreted by services.execute_report()'s dispatch for this report_type."),
    )
    is_active = models.BooleanField(
        _("is active"), default=True, db_index=True,
        help_text=_("Business-status flag (e.g. retired report), independent of soft delete."),
    )

    objects = SavedReportManager()
    active_objects = ActiveSavedReportManager()

    class Meta:
        ordering = ["name"]
        verbose_name = _("saved report")
        verbose_name_plural = _("saved reports")
        indexes = [
            models.Index(fields=["owner"], name="reports_savedreport_owner_idx"),
        ]

    def __str__(self):
        return self.name

    def manager_has_access(self, user):
        """CP6's documented per-object extension point, reused unchanged —
        see ``apps.activities.models.Task.manager_has_access()`` for the
        identical reasoning, applied to a `SavedReport`'s own ``owner``.
        """
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# ReportExecution
# --------------------------------------------------------------------------


class ReportExecutionQuerySet(SoftDeleteQuerySet):
    def for_report(self, report):
        return self.filter(report=report)

    def latest_for_report(self, report):
        return self.for_report(report).order_by("-created_at").first()


class ReportExecutionManager(models.Manager.from_queryset(ReportExecutionQuerySet)):
    """``ReportExecution.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveReportExecutionManager(ReportExecutionManager):
    def get_queryset(self):
        return super().get_queryset().active()


class ReportExecution(SoftDeleteTimeStampedModel):
    """One run of a `SavedReport` — created and driven entirely by
    ``services.execute_report()``; there is no create endpoint (see
    ``views.py``), the same "system writes it, a client only reads it"
    integrity boundary CP15's `CommunicationLog` established.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        RUNNING = "RUNNING", _("Running")
        COMPLETED = "COMPLETED", _("Completed")
        FAILED = "FAILED", _("Failed")

    report = models.ForeignKey(
        SavedReport,
        verbose_name=_("report"),
        on_delete=models.CASCADE,
        related_name="executions",
    )
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("executed by"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="report_executions",
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    result_data = models.JSONField(_("result data"), default=dict, blank=True)
    row_count = models.PositiveIntegerField(_("row count"), null=True, blank=True)
    error_message = models.TextField(_("error message"), blank=True, default="")

    objects = ReportExecutionManager()
    active_objects = ActiveReportExecutionManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("report execution")
        verbose_name_plural = _("report executions")
        indexes = [
            models.Index(fields=["report", "status"], name="reports_execution_status_idx"),
        ]

    def __str__(self):
        return f"{self.report.name} [{self.status}] @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def owner(self):
        """Lets ``IsOwnerOrSuperAdmin.resolve_owner()`` (CP6) find this
        execution's owning user via the report it belongs to — see this
        module's own docstring.
        """
        return self.report.owner

    def manager_has_access(self, user):
        """Delegates to the owning ``SavedReport``'s own hook — see
        ``SavedReport.manager_has_access()``.
        """
        return self.report.manager_has_access(user)


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------


class DashboardQuerySet(SoftDeleteQuerySet):
    def by_owner(self, user):
        return self.filter(owner=user)


class DashboardManager(models.Manager.from_queryset(DashboardQuerySet)):
    """``Dashboard.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveDashboardManager(DashboardManager):
    def get_queryset(self):
        return super().get_queryset().active()


class Dashboard(SoftDeleteTimeStampedModel):
    """A named collection of `DashboardWidget`s. At most one `is_default`
    dashboard PER OWNER — enforced by a partial `UniqueConstraint`, the
    same technique CP9's `ContactPerson` established for "at most one
    primary contact per customer".
    """

    name = models.CharField(_("name"), max_length=200)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_dashboards",
    )
    is_default = models.BooleanField(_("is default"), default=False)

    objects = DashboardManager()
    active_objects = ActiveDashboardManager()

    class Meta:
        ordering = ["name"]
        verbose_name = _("dashboard")
        verbose_name_plural = _("dashboards")
        constraints = [
            models.UniqueConstraint(
                fields=["owner"],
                condition=models.Q(is_default=True),
                name="reports_dashboard_unique_default_per_owner",
            ),
        ]
        indexes = [
            models.Index(fields=["owner"], name="reports_dashboard_owner_idx"),
        ]

    def __str__(self):
        return self.name

    def manager_has_access(self, user):
        """See ``SavedReport.manager_has_access()`` — identical reasoning."""
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# DashboardWidget
# --------------------------------------------------------------------------


class DashboardWidgetQuerySet(SoftDeleteQuerySet):
    def for_dashboard(self, dashboard):
        return self.filter(dashboard=dashboard)


class DashboardWidgetManager(models.Manager.from_queryset(DashboardWidgetQuerySet)):
    """``DashboardWidget.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveDashboardWidgetManager(DashboardWidgetManager):
    def get_queryset(self):
        return super().get_queryset().active()


class DashboardWidget(SoftDeleteTimeStampedModel):
    """One tile on a `Dashboard`, visualizing a `SavedReport`'s latest
    execution.
    """

    class WidgetType(models.TextChoices):
        CHART = "CHART", _("Chart")
        TABLE = "TABLE", _("Table")
        METRIC = "METRIC", _("Metric")

    dashboard = models.ForeignKey(
        Dashboard,
        verbose_name=_("dashboard"),
        on_delete=models.CASCADE,
        related_name="widgets",
    )
    report = models.ForeignKey(
        SavedReport,
        verbose_name=_("report"),
        on_delete=models.CASCADE,
        related_name="widgets",
    )
    widget_type = models.CharField(
        _("widget type"), max_length=10, choices=WidgetType.choices, default=WidgetType.TABLE
    )
    title = models.CharField(_("title"), max_length=200)
    position = models.PositiveIntegerField(_("position"), default=0)
    configuration = models.JSONField(
        _("configuration"), default=dict, blank=True,
        help_text=_("Widget-specific display config (e.g. chart type, color) — opaque to the backend, interpreted by the frontend."),
    )

    objects = DashboardWidgetManager()
    active_objects = ActiveDashboardWidgetManager()

    class Meta:
        ordering = ["dashboard", "position"]
        verbose_name = _("dashboard widget")
        verbose_name_plural = _("dashboard widgets")
        indexes = [
            models.Index(fields=["dashboard", "position"], name="reports_widget_dash_pos_idx"),
        ]

    def __str__(self):
        return f"{self.dashboard.name} / {self.title}"

    @property
    def owner(self):
        """Lets ``IsOwnerOrSuperAdmin.resolve_owner()`` (CP6) find this
        widget's owning user via the dashboard it belongs to — same
        delegation pattern as ``ReportExecution.owner``.
        """
        return self.dashboard.owner

    def manager_has_access(self, user):
        """Delegates to the owning ``Dashboard``'s own hook — see
        ``Dashboard.manager_has_access()``.
        """
        return self.dashboard.manager_has_access(user)
