"""CP17: tests for apps/workflows/services.py."""
import pytest

from apps.workflows.models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger
from apps.workflows.services import (
    add_action,
    add_trigger,
    create_workflow,
    evaluate_and_run,
    evaluate_conditions,
    managed_user_ids,
    run_workflow,
    scope_queryset_for_user,
    trigger_matches,
)

# --------------------------------------------------------------------------
# No database required — pure condition evaluation
# --------------------------------------------------------------------------


def test_managed_user_ids_and_scope_queryset_for_user_are_reexported_from_crm():
    from apps.crm import services as crm_services

    assert managed_user_ids is crm_services.managed_user_ids
    assert scope_queryset_for_user is crm_services.scope_queryset_for_user


def test_evaluate_conditions_empty_always_matches():
    class Entity:
        status = "NEW"

    assert evaluate_conditions(Entity(), {}) is True
    assert evaluate_conditions(Entity(), None) is True


def test_evaluate_conditions_matches_equal_field():
    class Entity:
        status = "QUALIFIED"

    assert evaluate_conditions(Entity(), {"field": "status", "equals": "QUALIFIED"}) is True


def test_evaluate_conditions_rejects_unequal_field():
    class Entity:
        status = "NEW"

    assert evaluate_conditions(Entity(), {"field": "status", "equals": "QUALIFIED"}) is False


def test_evaluate_conditions_missing_field_on_entity_does_not_match():
    class Entity:
        pass

    assert evaluate_conditions(Entity(), {"field": "status", "equals": "QUALIFIED"}) is False


def test_trigger_matches_rejects_wrong_trigger_type():
    class Entity:
        pass

    trigger = WorkflowTrigger(trigger_type=WorkflowTrigger.TriggerType.ON_UPDATE)
    assert trigger_matches(trigger, Entity(), event_type=WorkflowTrigger.TriggerType.ON_CREATE) is False


def test_every_action_type_has_a_registered_dispatcher():
    from apps.workflows.services import _ACTION_DISPATCHERS

    for action_type in WorkflowAction.ActionType.values:
        assert action_type in _ACTION_DISPATCHERS


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_workflow_basic(employee):
    workflow = create_workflow("Onboarding", owner=employee)
    assert workflow.owner_id == employee.id


@pytest.mark.django_db
def test_add_trigger_basic(workflow):
    trigger = add_trigger(workflow, WorkflowTrigger.TriggerType.ON_CREATE)
    assert trigger.workflow_id == workflow.id


@pytest.mark.django_db
def test_add_action_auto_assigns_position(workflow):
    first = add_action(workflow, WorkflowAction.ActionType.LOG_ACTIVITY)
    second = add_action(workflow, WorkflowAction.ActionType.LOG_ACTIVITY)
    assert first.position == 0
    assert second.position == 1


@pytest.mark.django_db
def test_add_action_respects_explicit_position(workflow):
    action = add_action(workflow, WorkflowAction.ActionType.LOG_ACTIVITY, position=5)
    assert action.position == 5


@pytest.mark.django_db
def test_trigger_matches_checks_content_type(workflow, customer):
    from django.contrib.contenttypes.models import ContentType

    from apps.crm.models import Customer, Lead

    trigger = add_trigger(
        workflow, WorkflowTrigger.TriggerType.ON_CREATE, content_type=ContentType.objects.get_for_model(Customer)
    )
    lead = Lead(company_name="X", contact_name="Y")

    assert trigger_matches(trigger, customer, event_type=WorkflowTrigger.TriggerType.ON_CREATE) is True
    assert trigger_matches(trigger, lead, event_type=WorkflowTrigger.TriggerType.ON_CREATE) is False


@pytest.mark.django_db
def test_run_workflow_log_activity_action_completes(workflow, customer):
    from apps.activities.models import ActivityLog

    add_action(workflow, WorkflowAction.ActionType.LOG_ACTIVITY, configuration={"description": "Auto-logged"})

    execution = run_workflow(workflow, customer)

    assert execution.status == WorkflowExecution.Status.COMPLETED
    assert execution.result_data["actions"][0]["action_type"] == "LOG_ACTIVITY"
    assert ActivityLog.objects.filter(description="Auto-logged").exists()


@pytest.mark.django_db
def test_run_workflow_create_task_action_completes(workflow, customer):
    from apps.activities.models import Task

    add_action(workflow, WorkflowAction.ActionType.CREATE_TASK, configuration={"title": "Follow up"})

    execution = run_workflow(workflow, customer)

    assert execution.status == WorkflowExecution.Status.COMPLETED
    assert Task.objects.filter(title="Follow up").exists()
    task = Task.objects.get(title="Follow up")
    assert task.related_object == customer


@pytest.mark.django_db
def test_run_workflow_create_notification_action_completes(workflow, customer, employee):
    from apps.communications.models import Notification

    add_action(
        workflow, WorkflowAction.ActionType.CREATE_NOTIFICATION,
        configuration={"recipient_id": employee.id, "title": "New customer"},
    )

    execution = run_workflow(workflow, customer)

    assert execution.status == WorkflowExecution.Status.COMPLETED
    assert Notification.objects.filter(recipient=employee, title="New customer").exists()


@pytest.mark.django_db
def test_run_workflow_send_email_action_completes(workflow, customer):
    from apps.communications.models import EmailMessage, EmailTemplate

    template = EmailTemplate.objects.create(name="Welcome", subject="Hi {{name}}", body="Welcome!")
    add_action(
        workflow, WorkflowAction.ActionType.SEND_EMAIL,
        configuration={"template_id": template.id, "to_field": "email"},
    )

    execution = run_workflow(workflow, customer)

    assert execution.status == WorkflowExecution.Status.COMPLETED
    assert EmailMessage.objects.filter(template=template).exists()


@pytest.mark.django_db
def test_run_workflow_runs_actions_in_position_order(workflow, customer):
    add_action(
        workflow, WorkflowAction.ActionType.LOG_ACTIVITY, position=1, configuration={"description": "Second"}
    )
    add_action(
        workflow, WorkflowAction.ActionType.LOG_ACTIVITY, position=0, configuration={"description": "First"}
    )

    execution = run_workflow(workflow, customer)

    descriptions = [a["action_type"] for a in execution.result_data["actions"]]
    assert descriptions == ["LOG_ACTIVITY", "LOG_ACTIVITY"]
    # Confirm ordering via the actual ActivityLog rows created, not just the action_type list.
    from apps.activities.models import ActivityLog

    logs = list(ActivityLog.objects.filter(description__in=["First", "Second"]).order_by("created_at"))
    assert [log.description for log in logs] == ["First", "Second"]


@pytest.mark.django_db
def test_run_workflow_failure_marks_execution_failed_and_stops(workflow, customer):
    add_action(workflow, WorkflowAction.ActionType.CREATE_NOTIFICATION, configuration={"recipient_id": 999999})
    add_action(workflow, WorkflowAction.ActionType.LOG_ACTIVITY, configuration={"description": "Should not run"})

    execution = run_workflow(workflow, customer)

    assert execution.status == WorkflowExecution.Status.FAILED
    assert execution.error_message
    from apps.activities.models import ActivityLog

    assert not ActivityLog.objects.filter(description="Should not run").exists()


@pytest.mark.django_db
def test_run_workflow_records_content_type_and_object_id(workflow, customer):
    from django.contrib.contenttypes.models import ContentType

    execution = run_workflow(workflow, customer)

    assert execution.content_type == ContentType.objects.get_for_model(customer)
    assert execution.object_id == customer.pk


@pytest.mark.django_db
def test_evaluate_and_run_fires_matching_workflow(workflow, customer):
    from apps.activities.models import ActivityLog

    add_trigger(workflow, WorkflowTrigger.TriggerType.ON_CREATE)
    add_action(workflow, WorkflowAction.ActionType.LOG_ACTIVITY, configuration={"description": "Fired"})

    executions = evaluate_and_run(customer, event_type=WorkflowTrigger.TriggerType.ON_CREATE)

    assert len(executions) == 1
    assert executions[0].status == WorkflowExecution.Status.COMPLETED
    assert ActivityLog.objects.filter(description="Fired").exists()


@pytest.mark.django_db
def test_evaluate_and_run_skips_inactive_workflow(workflow, customer):
    workflow.is_active = False
    workflow.save()
    add_trigger(workflow, WorkflowTrigger.TriggerType.ON_CREATE)
    add_action(workflow, WorkflowAction.ActionType.LOG_ACTIVITY)

    executions = evaluate_and_run(customer, event_type=WorkflowTrigger.TriggerType.ON_CREATE)

    assert executions == []


@pytest.mark.django_db
def test_evaluate_and_run_returns_empty_when_nothing_matches(customer):
    assert evaluate_and_run(customer, event_type=WorkflowTrigger.TriggerType.ON_DELETE) == []
