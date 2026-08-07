"""CP17: django-filter ``FilterSet`` classes for the workflows API."""
import django_filters

from .models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger


class WorkflowFilterSet(django_filters.FilterSet):
    class Meta:
        model = Workflow
        fields = ["owner", "is_active"]


class WorkflowTriggerFilterSet(django_filters.FilterSet):
    class Meta:
        model = WorkflowTrigger
        fields = ["workflow", "trigger_type", "content_type"]


class WorkflowActionFilterSet(django_filters.FilterSet):
    class Meta:
        model = WorkflowAction
        fields = ["workflow", "action_type"]


class WorkflowExecutionFilterSet(django_filters.FilterSet):
    class Meta:
        model = WorkflowExecution
        fields = ["workflow", "trigger", "status"]
