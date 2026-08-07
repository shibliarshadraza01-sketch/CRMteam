"""CP8: tests for apps/organization/permissions.py.

No new role-comparison logic exists in this app — these tests verify (1)
the re-exports are genuinely the same CP6 objects, and (2) that CP6's
``IsOwnerOrSuperAdmin`` correctly resolves ownership/manager-access for
``Team``/``Membership`` via the ``owner`` property and
``manager_has_access()`` hook added in ``models.py``, using the same
DummyRequest/DummyView, no-database pattern established in CP6/CP7.
"""
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.organization import permissions as org_permissions
from apps.organization.models import Membership, Team

User = get_user_model()


class DummyRequest:
    def __init__(self, user):
        self.user = user


class DummyView:
    pass


def _user(role, email, pk):
    user = User(email=email, role=role)
    user.pk = pk
    return user


# --------------------------------------------------------------------------
# Re-export integrity — no duplicate permission logic
# --------------------------------------------------------------------------


def test_reexported_classes_are_the_same_objects_as_accounts_permissions():
    assert org_permissions.IsSuperAdmin is accounts_permissions.IsSuperAdmin
    assert org_permissions.IsManager is accounts_permissions.IsManager
    assert org_permissions.IsEmployee is accounts_permissions.IsEmployee
    assert org_permissions.IsManagerOrSuperAdmin is accounts_permissions.IsManagerOrSuperAdmin
    assert org_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin
    assert org_permissions.ReadOnlyOrSuperAdmin is accounts_permissions.ReadOnlyOrSuperAdmin


# --------------------------------------------------------------------------
# IsOwnerOrSuperAdmin against Team (owner = manager)
# --------------------------------------------------------------------------


def test_team_manager_passes_is_owner_or_super_admin():
    manager = _user(User.Role.MANAGER, "mgr@example.com", 1)
    team = Team(name="Alpha")
    team.manager = manager
    perm = org_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(manager), DummyView(), team) is True


def test_non_manager_employee_denied_on_team_they_do_not_manage():
    manager = _user(User.Role.MANAGER, "mgr@example.com", 1)
    other_employee = _user(User.Role.EMPLOYEE, "emp@example.com", 2)
    team = Team(name="Alpha")
    team.manager = manager
    perm = org_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(other_employee), DummyView(), team) is False


def test_super_admin_always_passes_on_team():
    admin = _user(User.Role.SUPER_ADMIN, "admin@example.com", 3)
    team = Team(name="Alpha")  # no manager assigned at all
    perm = org_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(admin), DummyView(), team) is True


# --------------------------------------------------------------------------
# IsOwnerOrSuperAdmin against Membership (owner = member; manager_has_access hook)
# --------------------------------------------------------------------------


def test_membership_owner_passes_is_owner_or_super_admin():
    member = _user(User.Role.EMPLOYEE, "member@example.com", 5)
    membership = Membership(user=member, team=Team(name="Alpha"))
    perm = org_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(member), DummyView(), membership) is True


def test_team_manager_passes_via_manager_has_access_hook():
    manager = _user(User.Role.MANAGER, "mgr@example.com", 1)
    member = _user(User.Role.EMPLOYEE, "member@example.com", 5)
    team = Team(name="Alpha")
    team.manager = manager
    membership = Membership(user=member, team=team)
    perm = org_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(manager), DummyView(), membership) is True


def test_unrelated_manager_denied_on_a_membership_they_do_not_manage():
    team_manager = _user(User.Role.MANAGER, "mgr@example.com", 1)
    other_manager = _user(User.Role.MANAGER, "other-mgr@example.com", 9)
    member = _user(User.Role.EMPLOYEE, "member@example.com", 5)
    team = Team(name="Alpha")
    team.manager = team_manager
    membership = Membership(user=member, team=team)
    perm = org_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(other_manager), DummyView(), membership) is False


def test_different_employee_denied_on_someone_elses_membership():
    member = _user(User.Role.EMPLOYEE, "member@example.com", 5)
    other_employee = _user(User.Role.EMPLOYEE, "other@example.com", 6)
    membership = Membership(user=member, team=Team(name="Alpha"))
    perm = org_permissions.IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(other_employee), DummyView(), membership) is False
