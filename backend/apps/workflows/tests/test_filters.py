"""CP17: tests for apps/workflows/filters.py."""
import pytest

from apps.workflows.filters import WorkflowActionFilterSet, WorkflowFilterSet
from apps.workflows.models import Workflow, WorkflowAction

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_workflow_filterset_declares_expected_fields():
    assert set(WorkflowFilterSet.Meta.fields) == {"owner", "is_active"}


def test_workflow_action_filterset_declares_expected_fields():
    assert set(WorkflowActionFilterSet.Meta.fields) == {"workflow", "action_type"}


def test_is_active_filter_builds_query_without_hitting_db():
    filterset = WorkflowFilterSet(data={"is_active": "true"}, queryset=Workflow.objects.all())
    assert filterset.is_valid()
    assert len(filterset.qs.query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_is_active_filter_matches_real_rows(employee):
    active = Workflow.objects.create(name="Active", owner=employee, is_active=True)
    Workflow.objects.create(name="Inactive", owner=employee, is_active=False)

    filterset = WorkflowFilterSet(data={"is_active": "true"}, queryset=Workflow.objects.all())

    assert list(filterset.qs) == [active]


@pytest.mark.django_db
def test_action_type_filter_matches_real_rows(workflow):
    matching = WorkflowAction.objects.create(workflow=workflow, action_type=WorkflowAction.ActionType.LOG_ACTIVITY)
    WorkflowAction.objects.create(workflow=workflow, action_type=WorkflowAction.ActionType.CREATE_TASK)

    filterset = WorkflowActionFilterSet(data={"action_type": "LOG_ACTIVITY"}, queryset=WorkflowAction.objects.all())

    assert list(filterset.qs) == [matching]
