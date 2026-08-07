"""Django admin registrations for the communications domain.

Every `ModelAdmin` mixes in CP7's `SoftDeleteTimeStampedAdminMixin` —
unfiltered queryset, `is_deleted` in `list_filter`, soft-delete/restore
bulk actions, read-only timestamp/audit fields, all for free.
`content_type` is deliberately NOT an `autocomplete_field` — see CP14's
`apps/activities/admin.py` docstring for the identical reasoning
(`ContentType` has no admin of its own registered).
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin

from .models import CommunicationLog, EmailMessage, EmailTemplate, Notification


@admin.register(EmailTemplate)
class EmailTemplateAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "subject", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("name", "subject")
    ordering = ("name",)


@admin.register(EmailMessage)
class EmailMessageAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("subject", "to_email", "status", "owner", "sent_at", "is_deleted")
    list_filter = ("status", "is_deleted")
    search_fields = ("subject", "to_email")
    autocomplete_fields = ("owner", "template")
    ordering = ("-created_at",)


@admin.register(Notification)
class NotificationAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "recipient", "notification_type", "is_read", "is_deleted")
    list_filter = ("notification_type", "is_read", "is_deleted")
    search_fields = ("title", "message")
    autocomplete_fields = ("recipient",)
    ordering = ("-created_at",)


@admin.register(CommunicationLog)
class CommunicationLogAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("channel", "summary", "actor", "occurred_at", "is_deleted")
    list_filter = ("channel", "is_deleted")
    search_fields = ("summary",)
    autocomplete_fields = ("actor",)
    ordering = ("-occurred_at",)
