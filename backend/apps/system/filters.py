"""CP19: django-filter ``FilterSet`` classes for the system API."""
import django_filters

from .models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting


class AuditLogFilterSet(django_filters.FilterSet):
    class Meta:
        model = AuditLog
        fields = ["actor", "action", "content_type", "object_id"]


class SystemSettingFilterSet(django_filters.FilterSet):
    class Meta:
        model = SystemSetting
        fields = ["is_active"]


class FeatureFlagFilterSet(django_filters.FilterSet):
    class Meta:
        model = FeatureFlag
        fields = ["is_enabled"]


class BackgroundJobFilterSet(django_filters.FilterSet):
    class Meta:
        model = BackgroundJob
        fields = ["job_type", "status", "owner"]
