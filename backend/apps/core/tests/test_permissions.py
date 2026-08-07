"""CP7: tests for apps/core/permissions.py.

CP7 does not reimplement any role-comparison logic — it only re-exports
CP6's permission classes and adds one composed class,
``CanRestoreOrHardDelete``. These tests therefore focus on: (1) confirming
the re-exports are genuinely the same CP6 classes/functions (no accidental
duplication), and (2) exercising ``CanRestoreOrHardDelete``'s behavior,
following the exact same DummyRequest/DummyView, no-database pattern
established in apps/accounts/tests/test_permissions.py (CP6).
"""
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.core import permissions as core_permissions
from apps.core.permissions import CanRestoreOrHardDelete

User = get_user_model()


class DummyRequest:
    def __init__(self, user, method="GET"):
        self.user = user
        self.method = method


class DummyView:
    pass


def _user(role):
    return User(email=f"{role.lower()}@example.com", role=role)


# --------------------------------------------------------------------------
# Re-export integrity — no duplicate permission logic
# --------------------------------------------------------------------------


def test_reexported_classes_are_the_same_objects_as_accounts_permissions():
    assert core_permissions.IsSuperAdmin is accounts_permissions.IsSuperAdmin
    assert core_permissions.IsManager is accounts_permissions.IsManager
    assert core_permissions.IsEmployee is accounts_permissions.IsEmployee
    assert core_permissions.IsManagerOrSuperAdmin is accounts_permissions.IsManagerOrSuperAdmin
    assert core_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin
    assert core_permissions.ReadOnlyOrSuperAdmin is accounts_permissions.ReadOnlyOrSuperAdmin


def test_reexported_utility_functions_are_the_same_objects():
    assert core_permissions.role_level is accounts_permissions.role_level
    assert core_permissions.role_at_least is accounts_permissions.role_at_least
    assert core_permissions.user_has_role_at_least is accounts_permissions.user_has_role_at_least
    assert core_permissions.is_super_admin is accounts_permissions.is_super_admin
    assert core_permissions.resolve_owner is accounts_permissions.resolve_owner
    assert core_permissions.manager_has_access is accounts_permissions.manager_has_access


# --------------------------------------------------------------------------
# CanRestoreOrHardDelete
# --------------------------------------------------------------------------


def test_can_restore_or_hard_delete_is_a_subclass_of_is_manager_or_super_admin():
    assert issubclass(CanRestoreOrHardDelete, accounts_permissions.IsManagerOrSuperAdmin)


def test_can_restore_or_hard_delete_allows_manager_and_super_admin():
    perm = CanRestoreOrHardDelete()
    view = DummyView()

    assert perm.has_permission(DummyRequest(_user(User.Role.MANAGER)), view) is True
    assert perm.has_permission(DummyRequest(_user(User.Role.SUPER_ADMIN)), view) is True


def test_can_restore_or_hard_delete_denies_employee():
    perm = CanRestoreOrHardDelete()
    assert perm.has_permission(DummyRequest(_user(User.Role.EMPLOYEE)), DummyView()) is False


def test_can_restore_or_hard_delete_has_a_specific_message():
    assert "restore" in CanRestoreOrHardDelete.message.lower()
