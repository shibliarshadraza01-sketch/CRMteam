"""CP16: URL routes for the reports API, mounted at /api/v1/reports/ by
config/urls.py.

    GET/POST          /api/v1/reports/saved-reports/
    GET/PATCH/DELETE  /api/v1/reports/saved-reports/<id>/
    POST              /api/v1/reports/saved-reports/<id>/restore/       (CP7 mixin)
    POST              /api/v1/reports/saved-reports/<id>/hard-delete/   (CP7 mixin)
    POST              /api/v1/reports/saved-reports/<id>/execute/

    GET               /api/v1/reports/report-executions/            (read-only)
    GET               /api/v1/reports/report-executions/<id>/

    GET/POST          /api/v1/reports/dashboards/
    GET/PATCH/DELETE  /api/v1/reports/dashboards/<id>/
    POST              /api/v1/reports/dashboards/<id>/restore/
    POST              /api/v1/reports/dashboards/<id>/hard-delete/
    POST              /api/v1/reports/dashboards/<id>/set-default/
    GET               /api/v1/reports/dashboards/company-summary/   (Super Admin only)

    GET/POST          /api/v1/reports/dashboard-widgets/
    GET/PATCH/DELETE  /api/v1/reports/dashboard-widgets/<id>/
    POST              /api/v1/reports/dashboard-widgets/<id>/restore/
    POST              /api/v1/reports/dashboard-widgets/<id>/hard-delete/

Built entirely from DRF's ``DefaultRouter``.
"""
from rest_framework.routers import DefaultRouter

from .views import DashboardViewSet, DashboardWidgetViewSet, ReportExecutionViewSet, SavedReportViewSet

app_name = "reports"

router = DefaultRouter()
router.register("saved-reports", SavedReportViewSet, basename="saved-report")
router.register("report-executions", ReportExecutionViewSet, basename="report-execution")
router.register("dashboards", DashboardViewSet, basename="dashboard")
router.register("dashboard-widgets", DashboardWidgetViewSet, basename="dashboard-widget")

urlpatterns = router.urls
