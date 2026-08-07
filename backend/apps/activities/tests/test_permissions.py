"""CP14: tests for apps/activities/permissions.py — confirms this app reuses
CP6's ``IsOwnerOrSuperAdmin`` unchanged, and that every model's ownership
(real ``owner``/``actor`` fields, or a delegating ``owner`` property) is
correctly discoverable by CP6's ``resolve_owner()``. All DB-free.
"""
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.accounts.permissions import resolve_owner
from apps.activities import permissions as activities_permissions
from apps.activities.models import ActivityLog, Event, Reminder, Task

User = get_user_model()


class DummyRequest:
    def __init__(self, user):
        self.user = user


class DummyView:
    pass


def _user(role, email):
    return User(email=email, role=role)


def test_reexported_class_is_the_same_object_as_accounts_permissions():
    assert activities_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin


def test_resolve_owner_finds_task_owner_field():
    owner = _user(User.Role.EMPLOYEE, "owner@example.com")
    assert resolve_owner(Task(owner=owner)) is owner


def test_resolve_owner_finds_event_owner_field():
    owner = _user(User.Role.EMPLOYEE, "owner2@example.com")
    assert resolve_owner(Event(owner=owner)) is owner


def test_resolve_owner_finds_activitylog_owner_property():
    actor = _user(User.Role.EMPLOYEE, "actor@example.com")
    assert resolve_owner(ActivityLog(actor=actor)) is actor


def test_resolve_owner_finds_reminder_owner_property_via_task():
    owner = _user(User.Role.EMPLOYEE, "owner3@example.com")
    reminder = Reminder(task=Task(owner=owner))
    assert resolve_owner(reminder) is owner


def test_owner_can_access_own_task():
    owner = _user(User.Role.EMPLOYEE, "e@example.com")
    perm = activities_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(owner), DummyView(), Task(owner=owner)) is True


def test_non_owner_employee_denied():
    owner = _user(User.Role.EMPLOYEE, "e1@example.com")
    other = _user(User.Role.EMPLOYEE, "e2@example.com")
    perm = activities_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(other), DummyView(), Task(owner=owner)) is False


def test_super_admin_can_access_any_task():
    owner = _user(User.Role.EMPLOYEE, "e3@example.com")
    admin = _user(User.Role.SUPER_ADMIN, "admin@example.com")
    perm = activities_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(admin), DummyView(), Task(owner=owner)) is True
