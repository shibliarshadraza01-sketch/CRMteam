"""Django admin registrations for the workflow automation domain.

Every `ModelAdmin` mixes in CP7's `SoftDeleteTimeStampedAdminMixin` —
unfiltered queryset, `is_deleted` in `list_filter`, soft-delete/restore
bulk actions, read-only timestamp/audit fields, all for free.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin

from .models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger


class WorkflowTriggerInline(admin.TabularInline):
    model = WorkflowTrigger
    extra = 0
    fields = ("trigger_type", "content_type", "conditions")
    show_change_link = True


class WorkflowActionInline(admin.TabularInline):
    model = WorkflowAction
    extra = 0
    fields = ("action_type", "position", "configuration")
    show_change_link = True


@admin.register(Workflow)
class WorkflowAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "owner", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("name", "description")
    autocomplete_fields = ("owner",)
    ordering = ("name",)
    inlines = [WorkflowTriggerInline, WorkflowActionInline]


@admin.register(WorkflowTrigger)
class WorkflowTriggerAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("workflow", "trigger_type", "content_type", "is_deleted")
    list_filter = ("trigger_type", "is_deleted")
    search_fields = ("workflow__name",)
    autocomplete_fields = ("workflow",)
    ordering = ("workflow",)


@admin.register(WorkflowAction)
class WorkflowActionAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("workflow", "action_type", "position", "is_deleted")
    list_filter = ("action_type", "is_deleted")
    search_fields = ("workflow__name",)
    autocomplete_fields = ("workflow",)
    ordering = ("workflow", "position")


@admin.register(WorkflowExecution)
class WorkflowExecutionAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("workflow", "status", "trigger", "created_at", "is_deleted")
    list_filter = ("status", "is_deleted")
    search_fields = ("workflow__name",)
    autocomplete_fields = ("workflow", "trigger")
    ordering = ("-created_at",)
