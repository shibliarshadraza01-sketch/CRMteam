"""CP17: tests for apps/workflows/serializers.py."""
import pytest
from rest_framework import serializers

from apps.workflows.serializers import (
    WorkflowActionSerializer,
    WorkflowDetailSerializer,
    WorkflowExecuteSerializer,
    WorkflowExecutionSerializer,
    WorkflowSerializer,
    WorkflowTriggerSerializer,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_workflow_serializer_fields():
    fields = WorkflowSerializer().fields
    assert {
        "id", "name", "description", "owner", "is_active",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_workflow_trigger_serializer_business_fields_writable():
    fields = WorkflowTriggerSerializer().fields
    for name in ("workflow", "trigger_type", "content_type", "conditions"):
        assert fields[name].read_only is False


def test_workflow_action_serializer_business_fields_writable():
    fields = WorkflowActionSerializer().fields
    for name in ("workflow", "action_type", "configuration", "position"):
        assert fields[name].read_only is False


def test_workflow_execution_serializer_is_entirely_read_only():
    for name, field in WorkflowExecutionSerializer().fields.items():
        assert field.read_only is True


def test_workflow_detail_serializer_nests_triggers_and_actions():
    fields = WorkflowDetailSerializer().fields
    assert isinstance(fields["triggers"], serializers.ListSerializer)
    assert isinstance(fields["actions"], serializers.ListSerializer)


def test_workflow_detail_serializer_is_entirely_read_only():
    for name, field in WorkflowDetailSerializer().fields.items():
        assert field.read_only is True


def test_workflow_execute_serializer_requires_content_type_and_object_id():
    fields = WorkflowExecuteSerializer().fields
    assert fields["content_type"].required is True
    assert fields["object_id"].required is True


# --------------------------------------------------------------------------
# Requires database — full serializer validation (FK fields query the DB)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_workflow_serializer_full_validation(employee):
    serializer = WorkflowSerializer(data={"name": "W", "owner": employee.pk})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_workflow_action_serializer_full_validation(workflow):
    serializer = WorkflowActionSerializer(data={"workflow": workflow.pk, "action_type": "LOG_ACTIVITY"})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_workflow_execute_serializer_full_validation(customer):
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(customer)
    serializer = WorkflowExecuteSerializer(data={"content_type": content_type.pk, "object_id": customer.pk})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_workflow_detail_serializer_output(workflow):
    from apps.workflows.services import add_action, add_trigger

    add_trigger(workflow, "MANUAL")
    add_action(workflow, "LOG_ACTIVITY")

    data = WorkflowDetailSerializer(workflow).data

    assert len(data["triggers"]) == 1
    assert len(data["actions"]) == 1
