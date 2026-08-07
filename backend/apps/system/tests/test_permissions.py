"""CP19: tests for apps/system/permissions.py. All DB-free."""
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.system import permissions as system_permissions
from apps.system.permissions import SystemConfigWritePermission

User = get_user_model()


class DummyRequest:
    def __init__(self, user, method="GET"):
        self.user = user
        self.method = method


class DummyView:
    pass


def _user(role, email):
    return User(email=email, role=role)


def test_reexported_classes_are_the_same_objects_as_accounts_permissions():
    assert system_permissions.IsManagerOrSuperAdmin is accounts_permissions.IsManagerOrSuperAdmin
    assert system_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin


def test_manager_or_super_admin_denies_employee():
    employee = _user(User.Role.EMPLOYEE, "e@example.com")
    assert system_permissions.IsManagerOrSuperAdmin().has_permission(DummyRequest(employee), DummyView()) is False


def test_manager_or_super_admin_allows_manager():
    manager = _user(User.Role.MANAGER, "m@example.com")
    assert system_permissions.IsManagerOrSuperAdmin().has_permission(DummyRequest(manager), DummyView()) is True


def test_system_config_write_permission_employee_can_read():
    perm = SystemConfigWritePermission()
    employee = _user(User.Role.EMPLOYEE, "e2@example.com")
    assert perm.has_permission(DummyRequest(employee, "GET"), DummyView()) is True


def test_system_config_write_permission_employee_cannot_write():
    perm = SystemConfigWritePermission()
    employee = _user(User.Role.EMPLOYEE, "e3@example.com")
    assert perm.has_permission(DummyRequest(employee, "POST"), DummyView()) is False


def test_system_config_write_permission_manager_can_write():
    perm = SystemConfigWritePermission()
    manager = _user(User.Role.MANAGER, "m2@example.com")
    assert perm.has_permission(DummyRequest(manager, "POST"), DummyView()) is True


def test_system_config_write_permission_anonymous_denied():
    class Anonymous:
        is_authenticated = False

    perm = SystemConfigWritePermission()
    assert perm.has_permission(DummyRequest(Anonymous(), "GET"), DummyView()) is False
