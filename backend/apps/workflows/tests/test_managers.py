"""CP17: tests for the querysets on apps/workflows/models.py.

NOTE: ``WorkflowTrigger.objects.for_entity_type()`` calls
``ContentType.objects.get_for_model()`` internally, which queries (or
consults a cache backed by an earlier query against) the real
``django_content_type`` table — NOT pure Python metadata, despite
"looking" like it. Its test lives in the DB-required section for exactly
that reason (the lesson CP14 discovered and CP15/CP16 applied
proactively — see BACKEND_LEARNING_GUIDE.md CP14 §7).
"""
import pytest

from apps.workflows.models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_workflow_active_filters_is_deleted_and_is_active_without_hitting_db():
    where_sql = str(Workflow.objects.active().query.where)
    assert "is_deleted" in where_sql
    assert "is_active" in where_sql


def test_workflow_by_owner_builds_filter_without_hitting_db():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert len(Workflow.objects.by_owner(User(pk=1)).query.where) > 0


def test_trigger_for_workflow_builds_filter_without_hitting_db():
    workflow = Workflow(pk=1, name="W")
    assert len(WorkflowTrigger.objects.for_workflow(workflow).query.where) > 0


def test_action_for_workflow_builds_filter_without_hitting_db():
    workflow = Workflow(pk=1, name="W")
    assert len(WorkflowAction.objects.for_workflow(workflow).query.where) > 0


def test_execution_for_workflow_builds_filter_without_hitting_db():
    workflow = Workflow(pk=1, name="W")
    assert len(WorkflowExecution.objects.for_workflow(workflow).query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_active_workflow_manager_excludes_inactive_and_deleted(employee):
    active = Workflow.objects.create(name="Active", owner=employee, is_active=True)
    Workflow.objects.create(name="Inactive", owner=employee, is_active=False)
    deleted = Workflow.objects.create(name="Deleted", owner=employee)
    deleted.soft_delete()

    names = set(Workflow.active_objects.values_list("name", flat=True))
    assert names == {"Active"}


@pytest.mark.django_db
def test_action_for_workflow_orders_by_position(workflow):
    second = WorkflowAction.objects.create(workflow=workflow, action_type=WorkflowAction.ActionType.LOG_ACTIVITY, position=1)
    first = WorkflowAction.objects.create(workflow=workflow, action_type=WorkflowAction.ActionType.LOG_ACTIVITY, position=0)

    assert list(WorkflowAction.objects.for_workflow(workflow)) == [first, second]


@pytest.mark.django_db
def test_trigger_for_entity_type_matches_real_rows(workflow, customer):
    from apps.crm.models import Customer, Lead

    matching = WorkflowTrigger.objects.create(
        workflow=workflow, trigger_type=WorkflowTrigger.TriggerType.ON_CREATE, content_type=None
    )
    from django.contrib.contenttypes.models import ContentType

    matching.content_type = ContentType.objects.get_for_model(Customer)
    matching.save()
    WorkflowTrigger.objects.create(
        workflow=workflow,
        trigger_type=WorkflowTrigger.TriggerType.ON_CREATE,
        content_type=ContentType.objects.get_for_model(Lead),
    )

    assert list(WorkflowTrigger.objects.for_entity_type(Customer)) == [matching]
