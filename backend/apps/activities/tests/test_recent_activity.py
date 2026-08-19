"""Staff-management pass: the Recent Activities feed.

Asserts the feed is built from REAL CRM state (never static text) and that
it respects the same three-tier scoping every list endpoint uses.
"""
import datetime

import pytest
from django.utils import timezone

from apps.activities.services import get_recent_activity

RECENT_URL = "/api/v1/activities/recent/"


@pytest.fixture
def team(db, organization, manager, employee):
    from apps.organization.models import Department, Membership, Team

    department = Department.objects.create(organization=organization, name="Recent Dept")
    team = Team.objects.create(department=department, name="Recent Team", manager=manager)
    Membership.objects.create(team=team, user=employee)
    return team


@pytest.fixture
def employee_lead(db, employee):
    from apps.crm.models import Lead

    return Lead.objects.create(company_name="Acme", contact_name="Wile E", owner=employee)


@pytest.fixture
def other_lead(db, other_employee):
    from apps.crm.models import Lead

    return Lead.objects.create(company_name="Hooli", contact_name="Gavin B", owner=other_employee)


def _kinds(entries):
    return {entry["kind"] for entry in entries}


def test_feed_reports_a_real_lead_assignment(employee, employee_lead):
    entries = get_recent_activity(employee)

    assert "LEAD_ASSIGNED" in _kinds(entries)
    entry = next(e for e in entries if e["kind"] == "LEAD_ASSIGNED")
    assert entry["entity_id"] == employee_lead.pk
    assert entry["entity_type"] == "lead"


def test_feed_reports_a_real_lead_conversion(employee, employee_lead, organization):
    from apps.crm.services import convert_lead

    convert_lead(employee_lead, organization, owner=employee)

    entries = get_recent_activity(employee)

    assert "LEAD_CONVERTED" in _kinds(entries)
    assert "CUSTOMER_CREATED" in _kinds(entries)


def test_feed_reports_check_in_and_check_out(employee):
    from apps.attendance.services import end_session, start_session

    session = start_session(employee)
    end_session(session)

    kinds = _kinds(get_recent_activity(employee))

    assert "CHECKED_IN" in kinds
    assert "CHECKED_OUT" in kinds


def test_feed_reports_a_scheduled_follow_up(employee):
    from apps.activities.services import create_task

    create_task("Call Acme back", owner=employee, due_date=timezone.now())

    assert "FOLLOW_UP_SCHEDULED" in _kinds(get_recent_activity(employee))


def test_employee_never_sees_another_employees_events(employee, employee_lead, other_lead):
    entries = get_recent_activity(employee)

    entity_ids = {(e["entity_type"], e["entity_id"]) for e in entries}
    assert ("lead", employee_lead.pk) in entity_ids
    assert ("lead", other_lead.pk) not in entity_ids


def test_manager_sees_their_own_team_but_not_outsiders(manager, employee, employee_lead, other_lead, team):
    entries = get_recent_activity(manager)

    entity_ids = {(e["entity_type"], e["entity_id"]) for e in entries}
    assert ("lead", employee_lead.pk) in entity_ids
    assert ("lead", other_lead.pk) not in entity_ids


def test_super_admin_sees_everything(super_admin, employee_lead, other_lead):
    entries = get_recent_activity(super_admin)

    entity_ids = {(e["entity_type"], e["entity_id"]) for e in entries}
    assert ("lead", employee_lead.pk) in entity_ids
    assert ("lead", other_lead.pk) in entity_ids


def test_user_created_is_super_admin_only(super_admin, employee, manager, employee_lead):
    assert "USER_CREATED" in _kinds(get_recent_activity(super_admin))
    assert "USER_CREATED" not in _kinds(get_recent_activity(manager))
    assert "USER_CREATED" not in _kinds(get_recent_activity(employee))


def test_entries_are_sorted_most_recent_first(super_admin, employee_lead, other_lead):
    entries = get_recent_activity(super_admin)

    timestamps = [entry["timestamp"] for entry in entries]
    assert timestamps == sorted(timestamps, reverse=True)


def test_endpoint_requires_authentication(api_client):
    assert api_client.get(RECENT_URL).status_code == 401


def test_endpoint_honours_the_limit(api_client, super_admin, employee_lead, other_lead):
    api_client.force_authenticate(super_admin)

    response = api_client.get(f"{RECENT_URL}?limit=1")

    assert response.status_code == 200
    assert len(response.data) == 1


def test_endpoint_ignores_a_nonsense_limit(api_client, super_admin, employee_lead):
    api_client.force_authenticate(super_admin)

    response = api_client.get(f"{RECENT_URL}?limit=not-a-number&days=abc")

    assert response.status_code == 200


def test_old_events_fall_outside_the_window(employee, employee_lead):
    entries = get_recent_activity(employee, days=1, now=timezone.now() + datetime.timedelta(days=30))

    assert entries == []
