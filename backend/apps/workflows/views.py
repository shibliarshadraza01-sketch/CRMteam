"""CP17: the workflow automation domain's REST API.

Every viewset reuses CP10's ``_CrmModelViewSet`` (``apps.crm.views``)
directly — all four models here have a real or delegating ``owner``, the
same cross-app reuse CP12/CP14/CP15/CP16 already established. No new
ownership-scoping logic anywhere in this module.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import assert_object_accessible
from apps.core.utils import stamp_audit_fields
from apps.crm.services import resolve_owner_for_create
from apps.crm.views import _CrmModelViewSet

from .filters import (
    WorkflowActionFilterSet,
    WorkflowExecutionFilterSet,
    WorkflowFilterSet,
    WorkflowTriggerFilterSet,
)
from .models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger
from .serializers import (
    WorkflowActionSerializer,
    WorkflowDetailSerializer,
    WorkflowExecuteSerializer,
    WorkflowExecutionSerializer,
    WorkflowSerializer,
    WorkflowTriggerSerializer,
)
from .services import add_action, run_workflow


class WorkflowViewSet(_CrmModelViewSet):
    """CRUD (via ``_CrmModelViewSet``) plus one custom action —
    ``execute`` — a thin wrapper around ``services.run_workflow()``, the
    same "custom actions are thin wrappers around services" shape as
    CP16's ``SavedReportViewSet.execute``.
    """

    base_manager = Workflow.objects
    base_active_manager = Workflow.active_objects
    serializer_class = WorkflowSerializer
    filterset_class = WorkflowFilterSet
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("owner")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("triggers", "actions")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WorkflowDetailSerializer
        return WorkflowSerializer

    def perform_create(self, serializer):
        """Defaults ``owner`` to the requesting user when not explicitly
        supplied — the same rule ``SavedReportViewSet``/``DashboardViewSet``
        (CP16) already apply.
        """
        super().perform_create(serializer)
        workflow = serializer.instance
        resolved_owner = resolve_owner_for_create(self.request.user, workflow.owner)
        if resolved_owner.pk != workflow.owner_id:
            workflow.owner = resolved_owner
            workflow.save(update_fields=["owner", "updated_at"])

    @extend_schema(request=WorkflowExecuteSerializer, responses={201: WorkflowExecutionSerializer})
    @action(detail=True, methods=["post"])
    def execute(self, request, *args, **kwargs):
        """``POST /workflows/<id>/execute/`` — ``{"content_type": <id>,
        "object_id": <id>}``. Runs this workflow's actions against the
        identified entity now (``services.run_workflow()``) and returns
        the resulting ``WorkflowExecution``, COMPLETED or FAILED.
        """
        workflow = self.get_object()
        input_serializer = WorkflowExecuteSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        content_type = input_serializer.validated_data["content_type"]
        object_id = input_serializer.validated_data["object_id"]
        entity = content_type.get_object_for_this_type(pk=object_id)

        execution = run_workflow(workflow, entity)
        serializer = WorkflowExecutionSerializer(execution)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkflowTriggerViewSet(_CrmModelViewSet):
    base_manager = WorkflowTrigger.objects
    base_active_manager = WorkflowTrigger.active_objects
    serializer_class = WorkflowTriggerSerializer
    filterset_class = WorkflowTriggerFilterSet
    owner_field = "workflow__owner"
    ordering_fields = ["created_at"]
    ordering = ["workflow", "id"]

    def get_queryset(self):
        return super().get_queryset().select_related("workflow", "workflow__owner", "content_type")


class WorkflowActionViewSet(_CrmModelViewSet):
    base_manager = WorkflowAction.objects
    base_active_manager = WorkflowAction.active_objects
    serializer_class = WorkflowActionSerializer
    filterset_class = WorkflowActionFilterSet
    owner_field = "workflow__owner"
    ordering_fields = ["position", "created_at"]
    ordering = ["workflow", "position"]

    def get_queryset(self):
        return super().get_queryset().select_related("workflow", "workflow__owner")

    def perform_create(self, serializer):
        """Routes creation through ``services.add_action()`` — real
        behavior: auto-assigns ``position`` when omitted, the same
        auto-ordering convenience CP12's ``QuoteItemViewSet``/CP16's
        ``DashboardWidgetViewSet`` established for their own item models.
        """
        data = dict(serializer.validated_data)
        workflow = data.pop("workflow")
        assert_object_accessible(self.request, workflow)
        action_type = data.pop("action_type")
        configuration = data.pop("configuration", None)
        position = data.pop("position", None)

        workflow_action = add_action(workflow, action_type, configuration=configuration, position=position)
        stamp_audit_fields(workflow_action, self.request.user, creating=True)
        workflow_action.save()
        serializer.instance = workflow_action


class WorkflowExecutionViewSet(_CrmModelViewSet):
    """Read-only — ``http_method_names`` excludes every write verb, so
    there is no create/update/delete/restore/hard-delete route (DRF
    returns 405 for any of them), matching this model's own "written
    automatically by ``run_workflow()``, never by a client" design — the
    same integrity-boundary pattern CP15's ``CommunicationLogViewSet``/
    CP16's ``ReportExecutionViewSet`` established.
    """

    base_manager = WorkflowExecution.objects
    base_active_manager = WorkflowExecution.active_objects
    serializer_class = WorkflowExecutionSerializer
    filterset_class = WorkflowExecutionFilterSet
    owner_field = "workflow__owner"
    http_method_names = ["get", "head", "options"]
    search_fields = ["workflow__name"]
    ordering_fields = ["created_at", "completed_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("workflow", "trigger", "content_type")
