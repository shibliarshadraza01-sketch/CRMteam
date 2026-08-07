"""CP13: tests for apps/catalog/permissions.py — the ``CatalogWritePermission``
composition (``ReadOnlyOrSuperAdmin | IsManagerOrSuperAdmin``, both CP6
classes, combined via DRF's own ``|`` operator — zero new comparison
logic). All DB-free — no database involved in permission checks that
never resolve an owner or query anything.
"""
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.catalog import permissions as catalog_permissions
from apps.catalog.permissions import CatalogWritePermission

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
    assert catalog_permissions.IsManagerOrSuperAdmin is accounts_permissions.IsManagerOrSuperAdmin
    assert catalog_permissions.ReadOnlyOrSuperAdmin is accounts_permissions.ReadOnlyOrSuperAdmin
    assert catalog_permissions.IsSuperAdmin is accounts_permissions.IsSuperAdmin


def test_employee_can_read():
    perm = CatalogWritePermission()
    employee = _user(User.Role.EMPLOYEE, "e@example.com")
    for method in ("GET", "HEAD", "OPTIONS"):
        assert perm.has_permission(DummyRequest(employee, method), DummyView()) is True


def test_employee_cannot_write():
    perm = CatalogWritePermission()
    employee = _user(User.Role.EMPLOYEE, "e@example.com")
    for method in ("POST", "PATCH", "DELETE"):
        assert perm.has_permission(DummyRequest(employee, method), DummyView()) is False


def test_manager_can_write():
    perm = CatalogWritePermission()
    manager = _user(User.Role.MANAGER, "m@example.com")
    for method in ("POST", "PATCH", "DELETE"):
        assert perm.has_permission(DummyRequest(manager, method), DummyView()) is True


def test_super_admin_can_write():
    perm = CatalogWritePermission()
    admin = _user(User.Role.SUPER_ADMIN, "a@example.com")
    assert perm.has_permission(DummyRequest(admin, "DELETE"), DummyView()) is True


def test_anonymous_denied_entirely():
    class Anonymous:
        is_authenticated = False

    perm = CatalogWritePermission()
    assert perm.has_permission(DummyRequest(Anonymous(), "GET"), DummyView()) is False
