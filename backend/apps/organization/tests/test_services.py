"""CP8: tests for apps/organization/services.py.

Every function here reads or writes real rows, so every test requires a
database and is honestly blocked in this environment along with every
other DB-dependent test since CP2.
"""
import pytest

from apps.organization.models import Department, Membership, Organization, Team
from apps.organization.services import (
    add_member,
    change_member_role,
    get_team_members,
    get_user_teams,
    is_member,
    remove_member,
    set_team_manager,
)


@pytest.fixture
def team(db):
    org = Organization.objects.create(name="Acme", slug="acme")
    dept = Department.objects.create(organization=org, name="Sales")
    return Team.objects.create(department=dept, name="Alpha")


@pytest.mark.django_db
def test_add_member_creates_a_membership(team, django_user_model):
    user = django_user_model.objects.create_user(email="u@example.com", password="x")

    membership, created = add_member(team, user)

    assert created is True
    assert membership.role == Membership.Role.MEMBER
    assert is_member(team, user) is True


@pytest.mark.django_db
def test_add_member_is_idempotent_and_does_not_change_role(team, django_user_model):
    user = django_user_model.objects.create_user(email="u@example.com", password="x")
    add_member(team, user, role=Membership.Role.LEAD)

    membership, created = add_member(team, user, role=Membership.Role.MEMBER)

    assert created is False
    assert membership.role == Membership.Role.LEAD  # unchanged


@pytest.mark.django_db
def test_remove_member_deletes_and_returns_true(team, django_user_model):
    user = django_user_model.objects.create_user(email="u@example.com", password="x")
    add_member(team, user)

    result = remove_member(team, user)

    assert result is True
    assert is_member(team, user) is False


@pytest.mark.django_db
def test_remove_member_returns_false_when_not_a_member(team, django_user_model):
    user = django_user_model.objects.create_user(email="u@example.com", password="x")

    assert remove_member(team, user) is False


@pytest.mark.django_db
def test_change_member_role_updates_existing_membership(team, django_user_model):
    user = django_user_model.objects.create_user(email="u@example.com", password="x")
    add_member(team, user, role=Membership.Role.MEMBER)

    membership = change_member_role(team, user, Membership.Role.LEAD)

    assert membership.role == Membership.Role.LEAD
    membership.refresh_from_db()
    assert membership.role == Membership.Role.LEAD


@pytest.mark.django_db
def test_change_member_role_raises_for_non_member(team, django_user_model):
    user = django_user_model.objects.create_user(email="u@example.com", password="x")

    with pytest.raises(Membership.DoesNotExist):
        change_member_role(team, user, Membership.Role.LEAD)


@pytest.mark.django_db
def test_set_team_manager_assigns_and_persists(team, django_user_model):
    manager = django_user_model.objects.create_user(
        email="mgr@example.com", password="x", role=django_user_model.Role.MANAGER
    )

    set_team_manager(team, manager)
    team.refresh_from_db()

    assert team.manager_id == manager.id


@pytest.mark.django_db
def test_set_team_manager_can_clear_manager(team, django_user_model):
    manager = django_user_model.objects.create_user(
        email="mgr@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    set_team_manager(team, manager)

    set_team_manager(team, None)
    team.refresh_from_db()

    assert team.manager_id is None


@pytest.mark.django_db
def test_get_user_teams_returns_only_teams_the_user_belongs_to(team, django_user_model):
    org = Organization.objects.create(name="Beta Co", slug="beta-co")
    dept = Department.objects.create(organization=org, name="Support")
    other_team = Team.objects.create(department=dept, name="Bravo")
    user = django_user_model.objects.create_user(email="u@example.com", password="x")
    add_member(team, user)

    teams = get_user_teams(user)

    assert list(teams) == [team]
    assert other_team not in teams


@pytest.mark.django_db
def test_get_team_members_filters_by_role(team, django_user_model):
    lead = django_user_model.objects.create_user(email="lead@example.com", password="x")
    member = django_user_model.objects.create_user(email="member@example.com", password="x")
    add_member(team, lead, role=Membership.Role.LEAD)
    add_member(team, member, role=Membership.Role.MEMBER)

    leads = get_team_members(team, role=Membership.Role.LEAD)
    everyone = get_team_members(team)

    assert leads.count() == 1
    assert leads.first().user == lead
    assert everyone.count() == 2
