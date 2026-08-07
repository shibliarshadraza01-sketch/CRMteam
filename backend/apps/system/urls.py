"""CP19: URL routes for the system API, mounted at /api/v1/system/ by
config/urls.py.

    GET               /api/v1/system/audit-logs/            (read-only, Manager+)
    GET               /api/v1/system/audit-logs/<id>/

    GET/POST          /api/v1/system/settings/
    GET/PATCH/DELETE  /api/v1/system/settings/<id>/
    POST              /api/v1/system/settings/<id>/restore/       (CP7 mixin)
    POST              /api/v1/system/settings/<id>/hard-delete/   (CP7 mixin)

    GET/POST          /api/v1/system/feature-flags/
    GET/PATCH/DELETE  /api/v1/system/feature-flags/<id>/
    POST              /api/v1/system/feature-flags/<id>/restore/
    POST              /api/v1/system/feature-flags/<id>/hard-delete/

    GET/POST          /api/v1/system/background-jobs/
    GET/PATCH/DELETE  /api/v1/system/background-jobs/<id>/
    POST              /api/v1/system/background-jobs/<id>/restore/
    POST              /api/v1/system/background-jobs/<id>/hard-delete/
    POST              /api/v1/system/background-jobs/<id>/start/
    POST              /api/v1/system/background-jobs/<id>/complete/
    POST              /api/v1/system/background-jobs/<id>/fail/

Built entirely from DRF's ``DefaultRouter``.
"""
from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, BackgroundJobViewSet, FeatureFlagViewSet, SystemSettingViewSet

app_name = "system"

router = DefaultRouter()
router.register("audit-logs", AuditLogViewSet, basename="audit-log")
router.register("settings", SystemSettingViewSet, basename="system-setting")
router.register("feature-flags", FeatureFlagViewSet, basename="feature-flag")
router.register("background-jobs", BackgroundJobViewSet, basename="background-job")

urlpatterns = router.urls
