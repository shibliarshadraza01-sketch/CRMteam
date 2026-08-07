"""CP16: django-filter ``FilterSet`` classes for the reports API."""
import django_filters

from .models import Dashboard, DashboardWidget, ReportExecution, SavedReport


class SavedReportFilterSet(django_filters.FilterSet):
    class Meta:
        model = SavedReport
        fields = ["report_type", "owner", "is_active"]


class ReportExecutionFilterSet(django_filters.FilterSet):
    class Meta:
        model = ReportExecution
        fields = ["report", "status", "executed_by"]


class DashboardFilterSet(django_filters.FilterSet):
    class Meta:
        model = Dashboard
        fields = ["owner", "is_default"]


class DashboardWidgetFilterSet(django_filters.FilterSet):
    class Meta:
        model = DashboardWidget
        fields = ["dashboard", "report", "widget_type"]
