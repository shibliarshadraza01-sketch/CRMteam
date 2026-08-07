"""Django admin registrations for the system/platform domain.

`SystemSetting`/`FeatureFlag`/`BackgroundJob` mix in CP7's
`SoftDeleteTimeStampedAdminMixin` like every other soft-deletable model
in this project. `AuditLog` does NOT — it has no soft-delete fields to
manage (see `models.py`) — and additionally disables add/change/delete
entirely in the admin: an audit trail a Django staff user could edit or
delete through the admin is not a trustworthy audit trail, the same
reasoning `views.py` applies at the API layer (no write endpoints of any
kind).
"""
from django.contrib import admin

from apps.core.admin import ReadOnlyTimestampsAdminMixin, SoftDeleteTimeStampedAdminMixin

from .models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyTimestampsAdminMixin, admin.ModelAdmin):
    list_display = ("action", "actor", "content_type", "object_id", "created_at")
    list_filter = ("action",)
    search_fields = ("description", "actor__email")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SystemSetting)
class SystemSettingAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("key", "is_active", "is_deleted")
    list_filter = ("is_active", "is_deleted")
    search_fields = ("key", "description")
    ordering = ("key",)


@admin.register(FeatureFlag)
class FeatureFlagAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("key", "name", "is_enabled", "rollout_percentage", "is_deleted")
    list_filter = ("is_enabled", "is_deleted")
    search_fields = ("key", "name", "description")
    ordering = ("key",)


@admin.register(BackgroundJob)
class BackgroundJobAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "job_type", "status", "owner", "created_at", "is_deleted")
    list_filter = ("job_type", "status", "is_deleted")
    search_fields = ("name", "job_type")
    autocomplete_fields = ("owner",)
    ordering = ("-created_at",)
