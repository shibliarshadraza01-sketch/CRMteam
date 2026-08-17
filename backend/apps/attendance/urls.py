"""URL routes for the attendance API, mounted at /api/v1/attendance/ by
config/urls.py.

    GET/PATCH/DELETE  /api/v1/attendance/shift-config/<id>/    (Super Admin write, everyone reads)
    GET/POST          /api/v1/attendance/shift-config/
    GET               /api/v1/attendance/shift-config/current/

    GET               /api/v1/attendance/sessions/                    (own, or team/company — role-scoped)
    GET               /api/v1/attendance/sessions/<id>/
    POST              /api/v1/attendance/sessions/start/
    POST              /api/v1/attendance/sessions/heartbeat/
    POST              /api/v1/attendance/sessions/break-start/
    POST              /api/v1/attendance/sessions/break-end/
    POST              /api/v1/attendance/sessions/end/
    GET               /api/v1/attendance/sessions/current/
    GET               /api/v1/attendance/sessions/daily-summary/
    GET               /api/v1/attendance/sessions/team-status/        (Manager+)
    GET               /api/v1/attendance/sessions/company-report/     (Super Admin)

Built entirely from DRF's ``DefaultRouter``.
"""
from rest_framework.routers import DefaultRouter

from .views import AttendanceSessionViewSet, ShiftConfigurationViewSet

app_name = "attendance"

router = DefaultRouter()
router.register("shift-config", ShiftConfigurationViewSet, basename="shift-config")
router.register("sessions", AttendanceSessionViewSet, basename="attendance-session")

urlpatterns = router.urls
