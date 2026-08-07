"""CP17: tests for apps/workflows/models.py."""
import pytest

from apps.workflows.models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_workflow_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in Workflow._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_workflow_str_returns_name():
    assert str(Workflow(name="Lead Welcome Sequence")) == "Lead Welcome Sequence"


def test_workflow_is_active_defaults_true():
    assert Workflow._meta.get_field("is_active").default is True


def test_workflow_execution_has_generic_relation_fields_reused_from_activities():
    from apps.activities.models import RelatedToEntityModel

    assert issubclass(WorkflowExecution, RelatedToEntityModel)
    field_names = {f.name for f in WorkflowExecution._meta.get_fields()}
    assert {"content_type", "object_id", "related_object"} <= field_names


def test_workflow_trigger_has_no_object_id_field():
    """WorkflowTrigger watches a TYPE, not one instance — see models.py's
    module docstring for why it doesn't reuse the full RelatedToEntityModel
    mixin.
    """
    field_names = {f.name for f in WorkflowTrigger._meta.get_fields()}
    assert "content_type" in field_names
    assert "object_id" not in field_names


def test_workflow_trigger_defaults_to_manual():
    assert WorkflowTrigger._meta.get_field("trigger_type").default == WorkflowTrigger.TriggerType.MANUAL


def test_workflow_trigger_owner_property_delegates_to_workflow_owner():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="owner@example.com")
    workflow = Workflow(name="W", owner=user)
    trigger = WorkflowTrigger(workflow=workflow)
    assert trigger.owner is user


def test_workflow_action_owner_property_delegates_to_workflow_owner():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="owner2@example.com")
    workflow = Workflow(name="W", owner=user)
    action = WorkflowAction(workflow=workflow)
    assert action.owner is user


def test_workflow_action_position_defaults_to_zero():
    assert WorkflowAction._meta.get_field("position").default == 0


def test_workflow_execution_owner_property_delegates_to_workflow_owner():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="owner3@example.com")
    workflow = Workflow(name="W", owner=user)
    execution = WorkflowExecution(workflow=workflow)
    assert execution.owner is user


def test_workflow_execution_status_defaults_to_pending():
    assert WorkflowExecution._meta.get_field("status").default == WorkflowExecution.Status.PENDING


def test_workflow_execution_str_includes_workflow_name_and_status():
    from django.utils import timezone

    workflow = Workflow(name="Onboarding")
    execution = WorkflowExecution(workflow=workflow, status=WorkflowExecution.Status.COMPLETED, created_at=timezone.now())
    assert "Onboarding" in str(execution)
    assert "COMPLETED" in str(execution)


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_workflow_create_and_retrieve(employee):
    w = Workflow.objects.create(name="Draft", owner=employee)
    assert Workflow.objects.get(pk=w.pk).is_active is True


@pytest.mark.django_db
def test_deleting_workflow_cascades_to_triggers_actions_and_executions(workflow, customer):
    from django.contrib.contenttypes.models import ContentType

    trigger = WorkflowTrigger.objects.create(workflow=workflow, trigger_type=WorkflowTrigger.TriggerType.MANUAL)
    action = WorkflowAction.objects.create(workflow=workflow, action_type=WorkflowAction.ActionType.LOG_ACTIVITY)
    execution = WorkflowExecution.objects.create(
        workflow=workflow, content_type=ContentType.objects.get_for_model(customer), object_id=customer.pk
    )

    workflow.delete()

    assert not WorkflowTrigger.objects.filter(pk=trigger.pk).exists()
    assert not WorkflowAction.objects.filter(pk=action.pk).exists()
    assert not WorkflowExecution.objects.filter(pk=execution.pk).exists()


@pytest.mark.django_db
def test_workflow_execution_attaches_to_customer_via_generic_fk(workflow, customer):
    from django.contrib.contenttypes.models import ContentType

    execution = WorkflowExecution.objects.create(
        workflow=workflow, content_type=ContentType.objects.get_for_model(customer), object_id=customer.pk
    )
    assert execution.related_object == customer


@pytest.mark.django_db
def test_workflow_manager_has_access_true_for_managed_owner(manager, employee, organization):
    from apps.organization.models import Department, Membership, Team

    department = Department.objects.create(organization=organization, name="Automation")
    team = Team.objects.create(department=department, name="Automation Team", manager=manager)
    Membership.objects.create(team=team, user=employee)

    workflow = Workflow.objects.create(name="W", owner=employee)

    assert workflow.manager_has_access(manager) is True
