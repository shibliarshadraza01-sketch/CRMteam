"""Django admin registrations for the activity layer.

Every ``ModelAdmin`` mixes in CP7's ``SoftDeleteTimeStampedAdminMixin`` —
unfiltered queryset, `is_deleted` in `list_filter`, soft-delete/restore bulk
actions, read-only timestamp/audit fields, all for free. ``content_type`` is
deliberately NOT an `autocomplete_field` — `ContentType` has no admin of its
own registered (Django doesn't register one by default), and the field is
already narrowed to five choices via `limit_choices_to` on the model, so a
plain select is simplest.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin

from .models import ActivityLog, Event, Reminder, Task


@admin.register(Task)
class TaskAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "owner", "assigned_to", "priority", "status", "due_date", "is_deleted")
    list_filter = ("status", "priority", "is_deleted")
    search_fields = ("title", "description")
    autocomplete_fields = ("owner", "assigned_to")
    ordering = ("due_date",)


@admin.register(Event)
class EventAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "owner", "start_at", "end_at", "recurrence_frequency", "is_deleted")
    list_filter = ("recurrence_frequency", "is_deleted")
    search_fields = ("title", "description", "location")
    autocomplete_fields = ("owner",)
    ordering = ("start_at",)


@admin.register(ActivityLog)
class ActivityLogAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("activity_type", "actor", "occurred_at", "is_deleted")
    list_filter = ("activity_type", "is_deleted")
    search_fields = ("description",)
    autocomplete_fields = ("actor",)
    ordering = ("-occurred_at",)


@admin.register(Reminder)
class ReminderAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("subject", "remind_at", "is_sent", "is_deleted")
    list_filter = ("is_sent", "is_deleted")
    search_fields = ("message", "task__title", "event__title")
    autocomplete_fields = ("task", "event")
    ordering = ("remind_at",)
