"""CP14: URL routes for the activities API, mounted at /api/v1/activities/
by config/urls.py.

    GET/POST          /api/v1/activities/tasks/
    GET/PATCH/DELETE  /api/v1/activities/tasks/<id>/
    POST              /api/v1/activities/tasks/<id>/restore/       (CP7 mixin)
    POST              /api/v1/activities/tasks/<id>/hard-delete/   (CP7 mixin)
    POST              /api/v1/activities/tasks/<id>/complete/
    POST              /api/v1/activities/tasks/<id>/cancel/
    POST              /api/v1/activities/tasks/<id>/reassign/

...and the same CRUD+restore+hard-delete shape for /events/ (plus
``/occurrences/``), /activity-logs/, and /reminders/ (plus
``/mark-sent/``). Built from DRF's ``DefaultRouter`` for the four
resources, plus one hand-written path for the standalone timeline
endpoint (``TimelineView`` isn't a per-resource CRUD viewset, so it isn't
router-registrable).
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ActivityLogViewSet, EventViewSet, ReminderViewSet, TaskViewSet, TimelineView

app_name = "activities"

router = DefaultRouter()
router.register("tasks", TaskViewSet, basename="task")
router.register("events", EventViewSet, basename="event")
router.register("activity-logs", ActivityLogViewSet, basename="activity-log")
router.register("reminders", ReminderViewSet, basename="reminder")

urlpatterns = [
    path("timeline/", TimelineView.as_view(), name="timeline"),
] + router.urls
