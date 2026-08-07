"""CP19: tests for apps/system/admin.py. Django's admin registry is
populated at import time — no database needed.
"""
from django.contrib import admin

from apps.core.admin import ReadOnlyTimestampsAdminMixin, SoftDeleteTimeStampedAdminMixin
from apps.system.admin import (
    AuditLogAdmin,
    BackgroundJobAdmin,
    FeatureFlagAdmin,
    SystemSettingAdmin,
)
from apps.system.models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting


def test_all_four_models_are_registered():
    assert AuditLog in admin.site._registry
    assert SystemSetting in admin.site._registry
    assert FeatureFlag in admin.site._registry
    assert BackgroundJob in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[AuditLog], AuditLogAdmin)
    assert isinstance(admin.site._registry[SystemSetting], SystemSettingAdmin)
    assert isinstance(admin.site._registry[FeatureFlag], FeatureFlagAdmin)
    assert isinstance(admin.site._registry[BackgroundJob], BackgroundJobAdmin)


def test_auditlog_admin_uses_readonly_mixin_not_soft_delete_mixin():
    assert issubclass(AuditLogAdmin, ReadOnlyTimestampsAdminMixin)
    assert not issubclass(AuditLogAdmin, SoftDeleteTimeStampedAdminMixin)


def test_auditlog_admin_disables_add_change_delete():
    admin_instance = admin.site._registry[AuditLog]
    assert admin_instance.has_add_permission(request=None) is False
    assert admin_instance.has_change_permission(request=None) is False
    assert admin_instance.has_delete_permission(request=None) is False


def test_other_three_admins_use_soft_delete_timestamped_mixin():
    for admin_class in (SystemSettingAdmin, FeatureFlagAdmin, BackgroundJobAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_admins_declare_search_fields():
    for model in (AuditLog, SystemSetting, FeatureFlag, BackgroundJob):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
