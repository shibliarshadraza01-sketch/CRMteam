"""CP17: URL routes for the workflows API, mounted at /api/v1/workflows/
by config/urls.py.

    GET/POST          /api/v1/workflows/workflows/
    GET/PATCH/DELETE  /api/v1/workflows/workflows/<id>/
    POST              /api/v1/workflows/workflows/<id>/restore/       (CP7 mixin)
    POST              /api/v1/workflows/workflows/<id>/hard-delete/   (CP7 mixin)
    POST              /api/v1/workflows/workflows/<id>/execute/

    GET/POST          /api/v1/workflows/triggers/
    GET/PATCH/DELETE  /api/v1/workflows/triggers/<id>/
    POST              /api/v1/workflows/triggers/<id>/restore/
    POST              /api/v1/workflows/triggers/<id>/hard-delete/

    GET/POST          /api/v1/workflows/actions/
    GET/PATCH/DELETE  /api/v1/workflows/actions/<id>/
    POST              /api/v1/workflows/actions/<id>/restore/
    POST              /api/v1/workflows/actions/<id>/hard-delete/

    GET               /api/v1/workflows/executions/            (read-only)
    GET               /api/v1/workflows/executions/<id>/

Built entirely from DRF's ``DefaultRouter``.
"""
from rest_framework.routers import DefaultRouter

from .views import WorkflowActionViewSet, WorkflowExecutionViewSet, WorkflowTriggerViewSet, WorkflowViewSet

app_name = "workflows"

router = DefaultRouter()
router.register("workflows", WorkflowViewSet, basename="workflow")
router.register("triggers", WorkflowTriggerViewSet, basename="workflow-trigger")
router.register("actions", WorkflowActionViewSet, basename="workflow-action")
router.register("executions", WorkflowExecutionViewSet, basename="workflow-execution")

urlpatterns = router.urls
