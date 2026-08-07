"""Django admin registrations for the reporting/dashboard domain.

Every `ModelAdmin` mixes in CP7's `SoftDeleteTimeStampedAdminMixin` —
unfiltered queryset, `is_deleted` in `list_filter`, soft-delete/restore
bulk actions, read-only timestamp/audit fields, all for free.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin

from .models import Dashboard, DashboardWidget, ReportExecution, SavedReport


@admin.register(SavedReport)
class SavedReportAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "report_type", "owner", "is_active", "is_deleted")
    list_filter = ("report_type", "is_active", "is_deleted")
    search_fields = ("name", "description")
    autocomplete_fields = ("owner",)
    ordering = ("name",)


@admin.register(ReportExecution)
class ReportExecutionAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("report", "status", "executed_by", "row_count", "created_at", "is_deleted")
    list_filter = ("status", "is_deleted")
    search_fields = ("report__name",)
    autocomplete_fields = ("report", "executed_by")
    ordering = ("-created_at",)


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0
    fields = ("report", "widget_type", "title", "position")
    autocomplete_fields = ("report",)
    show_change_link = True


@admin.register(Dashboard)
class DashboardAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "owner", "is_default", "is_deleted")
    list_filter = ("is_default", "is_deleted")
    search_fields = ("name",)
    autocomplete_fields = ("owner",)
    ordering = ("name",)
    inlines = [DashboardWidgetInline]


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "dashboard", "report", "widget_type", "position", "is_deleted")
    list_filter = ("widget_type", "is_deleted")
    search_fields = ("title", "dashboard__name", "report__name")
    autocomplete_fields = ("dashboard", "report")
    ordering = ("dashboard", "position")
