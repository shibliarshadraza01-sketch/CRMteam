"""CP17: end-to-end tests for the workflows API. Requires a real database."""
import pytest

from apps.workflows.models import Workflow, WorkflowAction, WorkflowExecution

pytestmark = pytest.mark.django_db

WORKFLOWS_URL = "/api/v1/workflows/workflows/"
TRIGGERS_URL = "/api/v1/workflows/triggers/"
ACTIONS_URL = "/api/v1/workflows/actions/"
EXECUTIONS_URL = "/api/v1/workflows/executions/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# Workflow CRUD + ownership scoping
# --------------------------------------------------------------------------


def test_unauthenticated_denied(api_client):
    response = api_client.get(WORKFLOWS_URL)
    assert response.status_code == 401


def test_employee_can_create_and_owns_it_by_default(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(WORKFLOWS_URL, {"name": "My Workflow"})
    assert response.status_code == 201
    assert response.data["owner"] == employee.id


def test_employee_cannot_see_another_employees_workflow(api_client, employee, other_employee):
    Workflow.objects.create(name="Not mine", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(WORKFLOWS_URL)

    assert response.data["count"] == 0


def test_super_admin_sees_every_workflow(api_client, super_admin, workflow):
    api_client.force_authenticate(super_admin)
    response = api_client.get(WORKFLOWS_URL)
    assert response.data["count"] == 1


def test_put_not_allowed(api_client, employee, workflow):
    api_client.force_authenticate(employee)
    response = api_client.put(_detail(WORKFLOWS_URL, workflow.pk), {"name": "X"})
    assert response.status_code == 405


def test_delete_soft_deletes(api_client, employee, workflow):
    api_client.force_authenticate(employee)
    response = api_client.delete(_detail(WORKFLOWS_URL, workflow.pk))
    assert response.status_code == 204
    workflow.refresh_from_db()
    assert workflow.is_deleted is True


def test_retrieve_workflow_uses_detail_serializer(api_client, employee, workflow, customer):
    from apps.workflows.services import add_action, add_trigger

    add_trigger(workflow, "MANUAL")
    add_action(workflow, "LOG_ACTIVITY")
    api_client.force_authenticate(employee)

    response = api_client.get(_detail(WORKFLOWS_URL, workflow.pk))

    assert response.status_code == 200
    assert len(response.data["triggers"]) == 1
    assert len(response.data["actions"]) == 1


# --------------------------------------------------------------------------
# execute action + WorkflowExecution read-only endpoint
# --------------------------------------------------------------------------


def test_execute_action_creates_completed_execution(api_client, employee, workflow, customer):
    from django.contrib.contenttypes.models import ContentType

    from apps.workflows.services import add_action

    add_action(workflow, "LOG_ACTIVITY")
    content_type = ContentType.objects.get_for_model(customer)
    api_client.force_authenticate(employee)

    response = api_client.post(
        f"{_detail(WORKFLOWS_URL, workflow.pk)}execute/", {"content_type": content_type.pk, "object_id": customer.pk}
    )

    assert response.status_code == 201
    assert response.data["status"] == "COMPLETED"
    assert WorkflowExecution.objects.filter(workflow=workflow).exists()


def test_execute_action_requires_content_type_and_object_id(api_client, employee, workflow):
    api_client.force_authenticate(employee)
    response = api_client.post(f"{_detail(WORKFLOWS_URL, workflow.pk)}execute/")
    assert response.status_code == 400


def test_workflow_execution_has_no_create_endpoint(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(EXECUTIONS_URL, {"workflow": 1})
    assert response.status_code == 405


def test_employee_sees_only_executions_of_their_own_workflows(api_client, employee, other_employee, customer):
    from apps.workflows.services import create_workflow, run_workflow

    mine = create_workflow("Mine", owner=employee)
    theirs = create_workflow("Theirs", owner=other_employee)
    run_workflow(mine, customer)
    run_workflow(theirs, customer)
    api_client.force_authenticate(employee)

    response = api_client.get(EXECUTIONS_URL)

    assert response.data["count"] == 1


# --------------------------------------------------------------------------
# Trigger + Action CRUD
# --------------------------------------------------------------------------


def test_create_trigger(api_client, employee, workflow):
    api_client.force_authenticate(employee)
    response = api_client.post(TRIGGERS_URL, {"workflow": workflow.pk, "trigger_type": "MANUAL"})
    assert response.status_code == 201


def test_create_action_auto_assigns_position(api_client, employee, workflow):
    api_client.force_authenticate(employee)
    first = api_client.post(ACTIONS_URL, {"workflow": workflow.pk, "action_type": "LOG_ACTIVITY"})
    second = api_client.post(ACTIONS_URL, {"workflow": workflow.pk, "action_type": "LOG_ACTIVITY"})
    assert first.data["position"] == 0
    assert second.data["position"] == 1


def test_employee_cannot_see_actions_on_someone_elses_workflow(api_client, employee, other_employee):
    other_workflow = Workflow.objects.create(name="Theirs", owner=other_employee)
    WorkflowAction.objects.create(workflow=other_workflow, action_type=WorkflowAction.ActionType.LOG_ACTIVITY)
    api_client.force_authenticate(employee)

    response = api_client.get(ACTIONS_URL)

    assert response.data["count"] == 0


# --------------------------------------------------------------------------
# Search / filter / ordering / pagination
# --------------------------------------------------------------------------


def test_search_workflows_by_name(api_client, employee):
    Workflow.objects.create(name="Lead Nurture Sequence", owner=employee)
    Workflow.objects.create(name="Other", owner=employee)

    api_client.force_authenticate(employee)
    response = api_client.get(WORKFLOWS_URL, {"search": "Nurture"})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Lead Nurture Sequence"}


def test_pagination_default_page_size_is_20(api_client, employee):
    for i in range(25):
        Workflow.objects.create(name=f"Workflow {i:03d}", owner=employee)
    api_client.force_authenticate(employee)

    response = api_client.get(WORKFLOWS_URL)

    assert len(response.data["results"]) == 20
    assert response.data["count"] == 25
