"""CP17: tests for apps/workflows/admin.py. Django's admin registry is
populated at import time — no database needed.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin
from apps.workflows.admin import (
    WorkflowActionAdmin,
    WorkflowAdmin,
    WorkflowExecutionAdmin,
    WorkflowTriggerAdmin,
)
from apps.workflows.models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger


def test_all_four_models_are_registered():
    assert Workflow in admin.site._registry
    assert WorkflowTrigger in admin.site._registry
    assert WorkflowAction in admin.site._registry
    assert WorkflowExecution in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[Workflow], WorkflowAdmin)
    assert isinstance(admin.site._registry[WorkflowTrigger], WorkflowTriggerAdmin)
    assert isinstance(admin.site._registry[WorkflowAction], WorkflowActionAdmin)
    assert isinstance(admin.site._registry[WorkflowExecution], WorkflowExecutionAdmin)


def test_every_workflows_admin_uses_soft_delete_timestamped_mixin():
    for admin_class in (WorkflowAdmin, WorkflowTriggerAdmin, WorkflowActionAdmin, WorkflowExecutionAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_workflow_admin_has_trigger_and_action_inlines():
    admin_instance = admin.site._registry[Workflow]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert WorkflowTrigger in inline_models
    assert WorkflowAction in inline_models


def test_admins_declare_search_fields():
    for model in (Workflow, WorkflowTrigger, WorkflowAction, WorkflowExecution):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
