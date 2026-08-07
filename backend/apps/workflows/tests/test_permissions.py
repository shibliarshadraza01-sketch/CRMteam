"""CP17: tests for apps/workflows/permissions.py. All DB-free."""
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.accounts.permissions import resolve_owner
from apps.workflows import permissions as workflows_permissions
from apps.workflows.models import Workflow, WorkflowAction, WorkflowExecution, WorkflowTrigger

User = get_user_model()


class DummyRequest:
    def __init__(self, user):
        self.user = user


class DummyView:
    pass


def _user(role, email):
    return User(email=email, role=role)


def test_reexported_class_is_the_same_object_as_accounts_permissions():
    assert workflows_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin


def test_resolve_owner_finds_workflow_owner_field():
    owner = _user(User.Role.EMPLOYEE, "o1@example.com")
    assert resolve_owner(Workflow(owner=owner)) is owner


def test_resolve_owner_finds_trigger_owner_property():
    owner = _user(User.Role.EMPLOYEE, "o2@example.com")
    workflow = Workflow(name="W", owner=owner)
    assert resolve_owner(WorkflowTrigger(workflow=workflow)) is owner


def test_resolve_owner_finds_action_owner_property():
    owner = _user(User.Role.EMPLOYEE, "o3@example.com")
    workflow = Workflow(name="W", owner=owner)
    assert resolve_owner(WorkflowAction(workflow=workflow)) is owner


def test_resolve_owner_finds_execution_owner_property():
    owner = _user(User.Role.EMPLOYEE, "o4@example.com")
    workflow = Workflow(name="W", owner=owner)
    assert resolve_owner(WorkflowExecution(workflow=workflow)) is owner


def test_owner_can_access_own_workflow():
    owner = _user(User.Role.EMPLOYEE, "e1@example.com")
    perm = workflows_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(owner), DummyView(), Workflow(owner=owner)) is True


def test_non_owner_employee_denied_workflow():
    owner = _user(User.Role.EMPLOYEE, "e2@example.com")
    other = _user(User.Role.EMPLOYEE, "e3@example.com")
    perm = workflows_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(other), DummyView(), Workflow(owner=owner)) is False


def test_super_admin_can_access_any_workflow():
    owner = _user(User.Role.EMPLOYEE, "e4@example.com")
    admin = _user(User.Role.SUPER_ADMIN, "admin@example.com")
    perm = workflows_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(admin), DummyView(), Workflow(owner=owner)) is True
