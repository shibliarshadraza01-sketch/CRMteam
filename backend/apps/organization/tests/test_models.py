"""CP8: tests for apps/organization/models.py.

Split, following the established CP4-CP7 pattern, into DB-free tests (field
definitions, Meta options, pure-Python properties/methods operating on
in-memory instances) and DB-dependent tests (persistence, constraints,
relationship traversal against real rows) — the latter honestly blocked by
the same missing-PostgreSQL issue as every DB-backed test since CP2.
"""
import pytest
from django.db import IntegrityError, models
from django.contrib.auth import get_user_model

from apps.organization.models import Department, Membership, Organization, Team

User = get_user_model()


def _unsaved_user(role=User.Role.EMPLOYEE, email="user@example.com"):
    return User(email=email, role=role)


# --------------------------------------------------------------------------
# No database required — field/Meta definitions
# --------------------------------------------------------------------------


def test_organization_fields():
    name = Organization._meta.get_field("name")
    slug = Organization._meta.get_field("slug")
    is_active = Organization._meta.get_field("is_active")

    assert name.unique is True
    assert slug.unique is True
    assert isinstance(slug, models.SlugField)
    assert is_active.default is True


def test_organization_inherits_timestamps_and_audit_from_core():
    field_names = {f.name for f in Organization._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by"} <= field_names


def test_organization_meta():
    assert Organization._meta.ordering == ["name"]
    assert str(Organization._meta.verbose_name) == "organization"


def test_department_fk_to_organization_has_correct_related_name():
    field = Department._meta.get_field("organization")
    assert field.remote_field.related_name == "departments"
    assert field.remote_field.on_delete is models.CASCADE


def test_department_unique_constraint_on_organization_and_name():
    constraint_names = {c.name for c in Department._meta.constraints}
    assert "organization_department_unique_org_name" in constraint_names


def test_department_has_index_on_organization_and_name():
    index_names = {idx.name for idx in Department._meta.indexes}
    assert "org_department_org_name_idx" in index_names


def test_team_fk_to_department_has_correct_related_name():
    field = Team._meta.get_field("department")
    assert field.remote_field.related_name == "teams"
    assert field.remote_field.on_delete is models.CASCADE


def test_team_manager_fk_is_nullable_and_set_null():
    field = Team._meta.get_field("manager")
    assert field.null is True
    assert field.blank is True
    assert field.remote_field.on_delete is models.SET_NULL
    assert field.remote_field.related_name == "teams_managed"


def test_team_unique_constraint_on_department_and_name():
    constraint_names = {c.name for c in Team._meta.constraints}
    assert "organization_team_unique_department_name" in constraint_names


def test_membership_role_choices():
    assert Membership.Role.LEAD == "LEAD"
    assert Membership.Role.MEMBER == "MEMBER"
    role_field = Membership._meta.get_field("role")
    assert role_field.default == Membership.Role.MEMBER


def test_membership_unique_constraint_on_user_and_team():
    constraint_names = {c.name for c in Membership._meta.constraints}
    assert "organization_membership_unique_user_team" in constraint_names


def test_membership_fk_related_names():
    user_field = Membership._meta.get_field("user")
    team_field = Membership._meta.get_field("team")
    assert user_field.remote_field.related_name == "team_memberships"
    assert team_field.remote_field.related_name == "memberships"


def test_membership_has_index_on_team_and_role():
    index_names = {idx.name for idx in Membership._meta.indexes}
    assert "org_membership_team_role_idx" in index_names


# --------------------------------------------------------------------------
# No database required — __str__ / properties / hooks on in-memory instances
# --------------------------------------------------------------------------


def test_organization_str():
    org = Organization(name="Acme Inc")
    assert str(org) == "Acme Inc"


def test_department_str_uses_organization_name():
    org = Organization(name="Acme Inc")
    dept = Department(organization=org, name="Sales")
    assert str(dept) == "Acme Inc / Sales"


def test_team_owner_property_resolves_to_manager():
    manager = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    team = Team(name="Alpha")
    team.manager = manager
    assert team.owner is manager


def test_team_owner_property_is_none_without_a_manager():
    team = Team(name="Alpha")
    assert team.owner is None


def test_membership_owner_property_resolves_to_user():
    user = _unsaved_user()
    membership = Membership(user=user)
    assert membership.owner is user


def test_membership_manager_has_access_true_when_user_manages_the_team():
    manager = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    manager.pk = 7
    team = Team(name="Alpha")
    team.manager = manager
    membership = Membership(team=team)

    assert membership.manager_has_access(manager) is True


def test_membership_manager_has_access_false_for_a_different_manager():
    team_manager = _unsaved_user(role=User.Role.MANAGER, email="mgr@example.com")
    team_manager.pk = 7
    other_manager = _unsaved_user(role=User.Role.MANAGER, email="other@example.com")
    other_manager.pk = 8
    team = Team(name="Alpha")
    team.manager = team_manager
    membership = Membership(team=team)

    assert membership.manager_has_access(other_manager) is False


def test_membership_manager_has_access_false_when_team_has_no_manager():
    team = Team(name="Alpha")
    membership = Membership(team=team)

    assert membership.manager_has_access(_unsaved_user()) is False


# --------------------------------------------------------------------------
# Requires database — persistence, constraints, relationships
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_organization_create_and_retrieve():
    org = Organization.objects.create(name="Acme Inc", slug="acme-inc")
    fetched = Organization.objects.get(pk=org.pk)
    assert fetched.name == "Acme Inc"
    assert fetched.is_active is True


@pytest.mark.django_db
def test_organization_name_must_be_unique():
    Organization.objects.create(name="Acme Inc", slug="acme-inc")
    with pytest.raises(IntegrityError):
        Organization.objects.create(name="Acme Inc", slug="acme-inc-2")


@pytest.mark.django_db
def test_organization_slug_must_be_unique():
    Organization.objects.create(name="Acme Inc", slug="acme")
    with pytest.raises(IntegrityError):
        Organization.objects.create(name="Acme Inc 2", slug="acme")


@pytest.mark.django_db
def test_department_unique_per_organization_but_not_globally():
    org1 = Organization.objects.create(name="Acme", slug="acme")
    org2 = Organization.objects.create(name="Globex", slug="globex")
    Department.objects.create(organization=org1, name="Sales")

    # Same name in a DIFFERENT organization is fine.
    Department.objects.create(organization=org2, name="Sales")

    # Same name in the SAME organization is not.
    with pytest.raises(IntegrityError):
        Department.objects.create(organization=org1, name="Sales")


@pytest.mark.django_db
def test_deleting_organization_cascades_to_departments():
    org = Organization.objects.create(name="Acme", slug="acme")
    dept = Department.objects.create(organization=org, name="Sales")

    org.delete()

    assert not Department.objects.filter(pk=dept.pk).exists()


@pytest.mark.django_db
def test_team_unique_per_department_but_not_globally():
    org = Organization.objects.create(name="Acme", slug="acme")
    dept1 = Department.objects.create(organization=org, name="Sales")
    dept2 = Department.objects.create(organization=org, name="Support")
    Team.objects.create(department=dept1, name="Alpha")

    Team.objects.create(department=dept2, name="Alpha")  # fine, different department

    with pytest.raises(IntegrityError):
        Team.objects.create(department=dept1, name="Alpha")


@pytest.mark.django_db
def test_deleting_team_manager_sets_null_not_cascade(django_user_model):
    org = Organization.objects.create(name="Acme", slug="acme")
    dept = Department.objects.create(organization=org, name="Sales")
    manager = django_user_model.objects.create_user(
        email="mgr@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    team = Team.objects.create(department=dept, name="Alpha", manager=manager)

    manager.delete()
    team.refresh_from_db()

    assert team.manager_id is None


@pytest.mark.django_db
def test_membership_unique_per_user_and_team(django_user_model):
    org = Organization.objects.create(name="Acme", slug="acme")
    dept = Department.objects.create(organization=org, name="Sales")
    team = Team.objects.create(department=dept, name="Alpha")
    user = django_user_model.objects.create_user(email="u@example.com", password="x")
    Membership.objects.create(user=user, team=team)

    with pytest.raises(IntegrityError):
        Membership.objects.create(user=user, team=team)


@pytest.mark.django_db
def test_deleting_team_cascades_to_memberships(django_user_model):
    org = Organization.objects.create(name="Acme", slug="acme")
    dept = Department.objects.create(organization=org, name="Sales")
    team = Team.objects.create(department=dept, name="Alpha")
    user = django_user_model.objects.create_user(email="u@example.com", password="x")
    membership = Membership.objects.create(user=user, team=team)

    team.delete()

    assert not Membership.objects.filter(pk=membership.pk).exists()


@pytest.mark.django_db
def test_reverse_relationships_traverse_the_full_hierarchy(django_user_model):
    org = Organization.objects.create(name="Acme", slug="acme")
    dept = Department.objects.create(organization=org, name="Sales")
    team = Team.objects.create(department=dept, name="Alpha")
    user = django_user_model.objects.create_user(email="u@example.com", password="x")
    Membership.objects.create(user=user, team=team)

    assert org.departments.count() == 1
    assert dept.teams.count() == 1
    assert team.memberships.count() == 1
    assert user.team_memberships.count() == 1
