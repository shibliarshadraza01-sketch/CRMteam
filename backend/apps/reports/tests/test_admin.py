"""CP16: tests for apps/reports/admin.py. Django's admin registry is
populated at import time — no database needed.
"""
from django.contrib import admin

from apps.reports.admin import DashboardAdmin, DashboardWidgetAdmin, ReportExecutionAdmin, SavedReportAdmin
from apps.reports.models import Dashboard, DashboardWidget, ReportExecution, SavedReport
from apps.core.admin import SoftDeleteTimeStampedAdminMixin


def test_all_four_models_are_registered():
    assert SavedReport in admin.site._registry
    assert ReportExecution in admin.site._registry
    assert Dashboard in admin.site._registry
    assert DashboardWidget in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[SavedReport], SavedReportAdmin)
    assert isinstance(admin.site._registry[ReportExecution], ReportExecutionAdmin)
    assert isinstance(admin.site._registry[Dashboard], DashboardAdmin)
    assert isinstance(admin.site._registry[DashboardWidget], DashboardWidgetAdmin)


def test_every_reports_admin_uses_soft_delete_timestamped_mixin():
    for admin_class in (SavedReportAdmin, ReportExecutionAdmin, DashboardAdmin, DashboardWidgetAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_dashboard_admin_has_widget_inline():
    admin_instance = admin.site._registry[Dashboard]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert DashboardWidget in inline_models


def test_admins_declare_search_fields():
    for model in (SavedReport, ReportExecution, Dashboard, DashboardWidget):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
