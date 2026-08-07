"""CP6: tests for the RBAC permission infrastructure in permissions.py/mixins.py.

Deliberately written to need NO database connection, following the CP4/CP5
pattern (see test_super_admin_access_code.py / test_session_utils.py): every
permission class's ``has_permission``/``has_object_permission`` operates
purely on an in-memory ``User`` instance (never saved, never queried) and a
``DummyRequest``/``DummyView`` stand-in, so these tests genuinely run and
pass in this environment despite PostgreSQL being unavailable — see
BACKEND_PROGRESS.md for why that matters here.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.accounts.mixins import ObjectOwnershipMixin, RolePermissionMixin
from apps.accounts.permissions import (
    IsEmployee,
    IsManager,
    IsManagerOrSuperAdmin,
    IsOwnerOrSuperAdmin,
    IsSuperAdmin,
    ReadOnlyOrSuperAdmin,
    is_super_admin,
    manager_has_access,
    resolve_owner,
    role_at_least,
    role_level,
    user_has_role_at_least,
)

User = get_user_model()


# --------------------------------------------------------------------------
# Test doubles — no DB, no DRF request cycle needed
# --------------------------------------------------------------------------


class AnonymousUser:
    """Minimal stand-in for django.contrib.auth.models.AnonymousUser."""

    is_authenticated = False
    role = None


class DummyRequest:
    def __init__(self, user, method="GET"):
        self.user = user
        self.method = method


class DummyView:
    pass


def _user(role, **extra):
    """An unsaved User instance — role checks never touch the database."""
    return User(email=f"{role.lower()}@example.com", role=role, **extra)


def employee():
    return _user(User.Role.EMPLOYEE)


def manager():
    return _user(User.Role.MANAGER)


def super_admin():
    return _user(User.Role.SUPER_ADMIN)


# --------------------------------------------------------------------------
# Role hierarchy utility functions
# --------------------------------------------------------------------------


def test_role_level_orders_roles_correctly():
    assert role_level(User.Role.EMPLOYEE) < role_level(User.Role.MANAGER)
    assert role_level(User.Role.MANAGER) < role_level(User.Role.SUPER_ADMIN)


def test_role_level_unknown_role_returns_none():
    assert role_level("NOT_A_REAL_ROLE") is None
    assert role_level(None) is None
    assert role_level("") is None


@pytest.mark.parametrize(
    "role,minimum,expected",
    [
        (User.Role.EMPLOYEE, User.Role.EMPLOYEE, True),
        (User.Role.MANAGER, User.Role.EMPLOYEE, True),
        (User.Role.SUPER_ADMIN, User.Role.EMPLOYEE, True),
        (User.Role.EMPLOYEE, User.Role.MANAGER, False),
        (User.Role.MANAGER, User.Role.MANAGER, True),
        (User.Role.SUPER_ADMIN, User.Role.MANAGER, True),
        (User.Role.MANAGER, User.Role.SUPER_ADMIN, False),
        (User.Role.SUPER_ADMIN, User.Role.SUPER_ADMIN, True),
    ],
)
def test_role_at_least_hierarchy_matrix(role, minimum, expected):
    assert role_at_least(role, minimum) is expected


def test_role_at_least_unknown_role_fails_closed():
    assert role_at_least("BOGUS", User.Role.EMPLOYEE) is False
    assert role_at_least(User.Role.SUPER_ADMIN, "BOGUS") is False


def test_user_has_role_at_least_rejects_unauthenticated_user():
    assert user_has_role_at_least(AnonymousUser(), User.Role.EMPLOYEE) is False


def test_user_has_role_at_least_rejects_none_user():
    assert user_has_role_at_least(None, User.Role.EMPLOYEE) is False


def test_user_has_role_at_least_accepts_qualifying_authenticated_user():
    assert user_has_role_at_least(manager(), User.Role.EMPLOYEE) is True
    assert user_has_role_at_least(manager(), User.Role.MANAGER) is True
    assert user_has_role_at_least(manager(), User.Role.SUPER_ADMIN) is False


def test_is_super_admin():
    assert is_super_admin(super_admin()) is True
    assert is_super_admin(manager()) is False
    assert is_super_admin(employee()) is False
    assert is_super_admin(AnonymousUser()) is False
    assert is_super_admin(None) is False


# --------------------------------------------------------------------------
# IsSuperAdmin
# --------------------------------------------------------------------------


def test_is_super_admin_permission_allows_only_super_admin():
    perm = IsSuperAdmin()
    view = DummyView()

    assert perm.has_permission(DummyRequest(super_admin()), view) is True
    assert perm.has_permission(DummyRequest(manager()), view) is False
    assert perm.has_permission(DummyRequest(employee()), view) is False


def test_is_super_admin_permission_denies_anonymous():
    perm = IsSuperAdmin()
    assert perm.has_permission(DummyRequest(AnonymousUser()), DummyView()) is False


# --------------------------------------------------------------------------
# IsManager (hierarchy: manager-or-above)
# --------------------------------------------------------------------------


def test_is_manager_permission_allows_manager_and_super_admin():
    perm = IsManager()
    view = DummyView()

    assert perm.has_permission(DummyRequest(manager()), view) is True
    assert perm.has_permission(DummyRequest(super_admin()), view) is True


def test_is_manager_permission_denies_employee_and_anonymous():
    perm = IsManager()
    view = DummyView()

    assert perm.has_permission(DummyRequest(employee()), view) is False
    assert perm.has_permission(DummyRequest(AnonymousUser()), view) is False


# --------------------------------------------------------------------------
# IsEmployee (hierarchy floor: any authenticated user)
# --------------------------------------------------------------------------


def test_is_employee_permission_allows_every_authenticated_role():
    perm = IsEmployee()
    view = DummyView()

    assert perm.has_permission(DummyRequest(employee()), view) is True
    assert perm.has_permission(DummyRequest(manager()), view) is True
    assert perm.has_permission(DummyRequest(super_admin()), view) is True


def test_is_employee_permission_denies_anonymous():
    perm = IsEmployee()
    assert perm.has_permission(DummyRequest(AnonymousUser()), DummyView()) is False


# --------------------------------------------------------------------------
# IsManagerOrSuperAdmin (explicit union — same result set as IsManager today)
# --------------------------------------------------------------------------


def test_is_manager_or_super_admin_allows_both_roles():
    perm = IsManagerOrSuperAdmin()
    view = DummyView()

    assert perm.has_permission(DummyRequest(manager()), view) is True
    assert perm.has_permission(DummyRequest(super_admin()), view) is True


def test_is_manager_or_super_admin_denies_employee_and_anonymous():
    perm = IsManagerOrSuperAdmin()
    view = DummyView()

    assert perm.has_permission(DummyRequest(employee()), view) is False
    assert perm.has_permission(DummyRequest(AnonymousUser()), view) is False


# --------------------------------------------------------------------------
# ReadOnlyOrSuperAdmin
# --------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
def test_read_only_or_super_admin_allows_any_authenticated_user_to_read(method):
    perm = ReadOnlyOrSuperAdmin()
    view = DummyView()

    assert perm.has_permission(DummyRequest(employee(), method=method), view) is True
    assert perm.has_permission(DummyRequest(manager(), method=method), view) is True
    assert perm.has_permission(DummyRequest(super_admin(), method=method), view) is True


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_read_only_or_super_admin_denies_write_to_non_super_admin(method):
    perm = ReadOnlyOrSuperAdmin()
    view = DummyView()

    assert perm.has_permission(DummyRequest(employee(), method=method), view) is False
    assert perm.has_permission(DummyRequest(manager(), method=method), view) is False


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_read_only_or_super_admin_allows_write_for_super_admin(method):
    perm = ReadOnlyOrSuperAdmin()
    assert perm.has_permission(DummyRequest(super_admin(), method=method), DummyView()) is True


def test_read_only_or_super_admin_denies_anonymous_read():
    perm = ReadOnlyOrSuperAdmin()
    assert perm.has_permission(DummyRequest(AnonymousUser(), method="GET"), DummyView()) is False


# --------------------------------------------------------------------------
# resolve_owner()
# --------------------------------------------------------------------------


class FakeResourceWithOwner:
    def __init__(self, owner):
        self.owner = owner


class FakeResourceWithUser:
    def __init__(self, user):
        self.user = user


class FakeResourceWithCreatedBy:
    def __init__(self, created_by):
        self.created_by = created_by


class FakeResourceWithNoOwner:
    pass


def test_resolve_owner_prefers_owner_attribute():
    u = employee()
    assert resolve_owner(FakeResourceWithOwner(u)) is u


def test_resolve_owner_falls_back_to_user_attribute():
    u = employee()
    assert resolve_owner(FakeResourceWithUser(u)) is u


def test_resolve_owner_falls_back_to_created_by_attribute():
    u = employee()
    assert resolve_owner(FakeResourceWithCreatedBy(u)) is u


def test_resolve_owner_returns_none_when_no_owner_attribute_present():
    assert resolve_owner(FakeResourceWithNoOwner()) is None


def test_resolve_owner_returns_the_user_itself_when_object_is_a_user():
    u = employee()
    assert resolve_owner(u) is u


# --------------------------------------------------------------------------
# manager_has_access() extension point
# --------------------------------------------------------------------------


def test_manager_has_access_defaults_to_false():
    # CP6 introduces no team/hierarchy models yet — documented as always
    # False until a future checkpoint gives it something to evaluate.
    assert manager_has_access(manager(), FakeResourceWithNoOwner()) is False


# --------------------------------------------------------------------------
# IsOwnerOrSuperAdmin — has_permission (authentication gate only)
# --------------------------------------------------------------------------


def test_is_owner_or_super_admin_has_permission_requires_authentication():
    perm = IsOwnerOrSuperAdmin()
    view = DummyView()

    assert perm.has_permission(DummyRequest(employee()), view) is True
    assert perm.has_permission(DummyRequest(AnonymousUser()), view) is False
    assert perm.has_permission(DummyRequest(None), view) is False


# --------------------------------------------------------------------------
# IsOwnerOrSuperAdmin — has_object_permission (the real ownership check)
# --------------------------------------------------------------------------


def test_is_owner_or_super_admin_allows_the_owner():
    perm = IsOwnerOrSuperAdmin()
    owner = employee()
    obj = FakeResourceWithOwner(owner)

    assert perm.has_object_permission(DummyRequest(owner), DummyView(), obj) is True


def test_is_owner_or_super_admin_denies_a_different_employee():
    perm = IsOwnerOrSuperAdmin()
    owner = employee()
    other = employee()
    obj = FakeResourceWithOwner(owner)

    assert perm.has_object_permission(DummyRequest(other), DummyView(), obj) is False


def test_is_owner_or_super_admin_always_allows_super_admin_override():
    perm = IsOwnerOrSuperAdmin()
    owner = employee()
    admin = super_admin()
    obj = FakeResourceWithOwner(owner)

    assert perm.has_object_permission(DummyRequest(admin), DummyView(), obj) is True


def test_is_owner_or_super_admin_super_admin_allowed_even_with_no_resolvable_owner():
    perm = IsOwnerOrSuperAdmin()
    admin = super_admin()
    obj = FakeResourceWithNoOwner()

    assert perm.has_object_permission(DummyRequest(admin), DummyView(), obj) is True


def test_is_owner_or_super_admin_denies_manager_without_explicit_access():
    # No team/hierarchy model exists yet (CP6 scope), so manager_has_access()
    # always returns False — a Manager who does not own the object is denied.
    perm = IsOwnerOrSuperAdmin()
    owner = employee()
    mgr = manager()
    obj = FakeResourceWithOwner(owner)

    assert perm.has_object_permission(DummyRequest(mgr), DummyView(), obj) is False


def test_is_owner_or_super_admin_allows_manager_via_per_object_hook():
    perm = IsOwnerOrSuperAdmin()
    owner = employee()
    mgr = manager()

    class ResourceWithManagerHook(FakeResourceWithOwner):
        def manager_has_access(self, user):
            return True

    obj = ResourceWithManagerHook(owner)

    assert perm.has_object_permission(DummyRequest(mgr), DummyView(), obj) is True


def test_is_owner_or_super_admin_denies_employee_with_no_resolvable_owner():
    perm = IsOwnerOrSuperAdmin()
    emp = employee()
    obj = FakeResourceWithNoOwner()

    assert perm.has_object_permission(DummyRequest(emp), DummyView(), obj) is False


def test_is_owner_or_super_admin_owner_check_uses_equality_not_identity():
    # Two distinct in-memory User instances representing "the same" row
    # (same pk) should compare equal via Django's Model.__eq__ — exercised
    # here with explicit pk values since neither instance is saved.
    owner = employee()
    owner.pk = 42
    same_user_different_instance = employee()
    same_user_different_instance.pk = 42

    obj = FakeResourceWithOwner(owner)
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(
        DummyRequest(same_user_different_instance), DummyView(), obj
    ) is True


# --------------------------------------------------------------------------
# RolePermissionMixin
# --------------------------------------------------------------------------


class _FakeGenericView:
    """Stands in for a DRF GenericAPIView's permission_classes machinery
    without needing the full APIView request/response cycle.
    """

    permission_classes = []

    def get_permissions(self):
        return [cls() for cls in self.permission_classes]


class ManagerOnlyView(RolePermissionMixin, _FakeGenericView):
    required_role = User.Role.MANAGER


class NoRoleDeclaredView(RolePermissionMixin, _FakeGenericView):
    permission_classes = [IsEmployee]


def test_role_permission_mixin_derives_permission_from_required_role():
    view = ManagerOnlyView()
    perms = view.get_permissions()

    assert len(perms) == 1
    assert isinstance(perms[0], IsManager)


def test_role_permission_mixin_is_noop_without_required_role():
    view = NoRoleDeclaredView()
    perms = view.get_permissions()

    assert len(perms) == 1
    assert isinstance(perms[0], IsEmployee)


def test_role_permission_mixin_prepends_rather_than_replaces():
    class CombinedView(RolePermissionMixin, _FakeGenericView):
        required_role = User.Role.SUPER_ADMIN
        permission_classes = [IsEmployee]

    perms = CombinedView().get_permissions()

    assert len(perms) == 2
    assert isinstance(perms[0], IsSuperAdmin)
    assert isinstance(perms[1], IsEmployee)


def test_role_permission_mixin_rejects_unrecognized_role():
    class BrokenView(RolePermissionMixin, _FakeGenericView):
        required_role = "NOT_A_REAL_ROLE"

    with pytest.raises(ValueError):
        BrokenView().get_permissions()


def test_role_permission_mixin_end_to_end_hierarchy_behavior():
    # Effective behavior check: a MANAGER-required view rejects an employee
    # and accepts a manager or super admin, driven purely by the mixin.
    view = ManagerOnlyView()
    perm = view.get_permissions()[0]

    assert perm.has_permission(DummyRequest(employee()), view) is False
    assert perm.has_permission(DummyRequest(manager()), view) is True
    assert perm.has_permission(DummyRequest(super_admin()), view) is True


# --------------------------------------------------------------------------
# ObjectOwnershipMixin
# --------------------------------------------------------------------------


class OwnedResourceView(ObjectOwnershipMixin, _FakeGenericView):
    permission_classes = [IsEmployee]


def test_object_ownership_mixin_prepends_is_owner_or_super_admin():
    perms = OwnedResourceView().get_permissions()

    assert len(perms) == 2
    assert isinstance(perms[0], IsOwnerOrSuperAdmin)
    assert isinstance(perms[1], IsEmployee)


# --------------------------------------------------------------------------
# Edge cases
# --------------------------------------------------------------------------


def test_inactive_user_role_checks_do_not_special_case_is_active():
    # Role permission classes intentionally check ONLY is_authenticated +
    # role — is_active enforcement is DRF/SimpleJWT's job (an inactive
    # user's token is already rejected before a view's permission_classes
    # ever run, per CP3's authenticate()/ModelBackend behavior). This test
    # documents that these classes do not duplicate that check.
    u = manager()
    u.is_active = False
    assert IsManager().has_permission(DummyRequest(u), DummyView()) is True


def test_role_hierarchy_matches_super_admin_inherits_everything():
    admin = super_admin()
    view = DummyView()

    for perm_cls in (IsEmployee, IsManager, IsSuperAdmin, IsManagerOrSuperAdmin):
        assert perm_cls().has_permission(DummyRequest(admin), view) is True


def test_role_hierarchy_matches_manager_inherits_employee_only():
    mgr = manager()
    view = DummyView()

    assert IsEmployee().has_permission(DummyRequest(mgr), view) is True
    assert IsManager().has_permission(DummyRequest(mgr), view) is True
    assert IsSuperAdmin().has_permission(DummyRequest(mgr), view) is False
