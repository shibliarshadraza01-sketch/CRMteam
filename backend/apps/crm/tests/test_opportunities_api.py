"""CP11: end-to-end tests for the Opportunity REST API — CRUD, stage
transitions, notes, activities, search, filtering, ordering. Requires a
real database (real HTTP requests via DRF's ``APIClient``, using
``force_authenticate()`` per the CP10-established shortcut).
"""
import datetime

import pytest

from apps.crm.opportunities import Opportunity, OpportunityActivity, OpportunityNote

pytestmark = pytest.mark.django_db

OPPS_URL = "/api/v1/crm/opportunities/"


def _detail(pk):
    return f"{OPPS_URL}{pk}/"


# --------------------------------------------------------------------------
# CRUD
# --------------------------------------------------------------------------


def test_create_opportunity(api_client, customer, manager):
    api_client.force_authenticate(manager)

    response = api_client.post(OPPS_URL, {"customer": customer.pk, "title": "Big Deal", "value": "5000.00"})

    assert response.status_code == 201
    opp = Opportunity.objects.get(pk=response.data["id"])
    assert opp.owner_id == manager.id  # defaulted via assign_owner()


def test_list_opportunities_returns_only_active_rows(api_client, super_admin, customer):
    visible = Opportunity.objects.create(customer=customer, title="Visible")
    deleted = Opportunity.objects.create(customer=customer, title="Deleted")
    deleted.soft_delete()
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL)

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"Visible"}


def test_retrieve_opportunity_uses_detail_serializer(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.get(_detail(opportunity.pk))

    assert response.status_code == 200
    assert "customer_name" in response.data
    assert "notes" in response.data
    assert "activities" in response.data


def test_patch_opportunity(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.patch(_detail(opportunity.pk), {"probability": 75})

    assert response.status_code == 200
    opportunity.refresh_from_db()
    assert opportunity.probability == 75


def test_put_opportunity_not_allowed(api_client, opportunity, owner):
    api_client.force_authenticate(owner)
    response = api_client.put(_detail(opportunity.pk), {"title": "New"})
    assert response.status_code == 405


def test_delete_opportunity_soft_deletes(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.delete(_detail(opportunity.pk))

    assert response.status_code == 204
    opportunity.refresh_from_db()
    assert opportunity.is_deleted is True


def test_patching_stage_to_won_directly_is_rejected(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.patch(_detail(opportunity.pk), {"stage": "WON"})

    assert response.status_code == 400
    assert "stage" in response.data


def test_employee_cannot_retrieve_someone_elses_opportunity(api_client, organization, employee, other_employee):
    from apps.crm.models import Customer

    theirs_customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs-api", owner=other_employee)
    theirs = Opportunity.objects.create(customer=theirs_customer, title="Theirs", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(_detail(theirs.pk))

    assert response.status_code == 404


# --------------------------------------------------------------------------
# Stage transitions
# --------------------------------------------------------------------------


def test_advance_stage_action(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.post(f"{_detail(opportunity.pk)}advance-stage/", {"stage": "QUALIFIED"})

    assert response.status_code == 200
    opportunity.refresh_from_db()
    assert opportunity.stage == Opportunity.Stage.QUALIFIED


def test_advance_stage_action_rejects_won(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.post(f"{_detail(opportunity.pk)}advance-stage/", {"stage": "WON"})

    assert response.status_code == 400


def test_mark_won_action(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.post(f"{_detail(opportunity.pk)}mark-won/")

    assert response.status_code == 200
    opportunity.refresh_from_db()
    assert opportunity.is_won is True
    assert opportunity.is_closed is True
    assert opportunity.actual_close_date == datetime.date.today()


def test_mark_won_action_twice_returns_400(api_client, opportunity, owner):
    api_client.force_authenticate(owner)
    api_client.post(f"{_detail(opportunity.pk)}mark-won/")

    response = api_client.post(f"{_detail(opportunity.pk)}mark-won/")

    assert response.status_code == 400


def test_mark_lost_action(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.post(f"{_detail(opportunity.pk)}mark-lost/")

    assert response.status_code == 200
    opportunity.refresh_from_db()
    assert opportunity.is_won is False
    assert opportunity.is_closed is True


def test_reopen_action(api_client, opportunity, owner):
    api_client.force_authenticate(owner)
    api_client.post(f"{_detail(opportunity.pk)}mark-won/")

    response = api_client.post(f"{_detail(opportunity.pk)}reopen/")

    assert response.status_code == 200
    opportunity.refresh_from_db()
    assert opportunity.is_closed is False
    assert opportunity.stage == Opportunity.Stage.NEW


def test_reopen_action_on_open_opportunity_returns_400(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.post(f"{_detail(opportunity.pk)}reopen/")

    assert response.status_code == 400


def test_advance_stage_requires_ownership(api_client, organization, employee, other_employee):
    from apps.crm.models import Customer

    theirs_customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs-stage", owner=other_employee)
    theirs = Opportunity.objects.create(customer=theirs_customer, title="Theirs", owner=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.post(f"{_detail(theirs.pk)}mark-won/")

    assert response.status_code == 404


# --------------------------------------------------------------------------
# Notes
# --------------------------------------------------------------------------


def test_list_notes_action(api_client, opportunity, owner):
    OpportunityNote.objects.create(opportunity=opportunity, content="Existing note")
    api_client.force_authenticate(owner)

    response = api_client.get(f"{_detail(opportunity.pk)}notes/")

    assert response.status_code == 200
    assert len(response.data) == 1


def test_create_note_action_stamps_author(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.post(f"{_detail(opportunity.pk)}notes/", {"content": "A new note"})

    assert response.status_code == 201
    note = OpportunityNote.objects.get(pk=response.data["id"])
    assert note.content == "A new note"
    assert note.created_by_id == owner.id


def test_notes_action_excludes_deleted_notes(api_client, opportunity, owner):
    visible = OpportunityNote.objects.create(opportunity=opportunity, content="Visible")
    deleted = OpportunityNote.objects.create(opportunity=opportunity, content="Deleted")
    deleted.soft_delete()
    api_client.force_authenticate(owner)

    response = api_client.get(f"{_detail(opportunity.pk)}notes/")

    contents = {row["content"] for row in response.data}
    assert contents == {"Visible"}


# --------------------------------------------------------------------------
# Activities
# --------------------------------------------------------------------------


def test_list_activities_action(api_client, opportunity, owner):
    OpportunityActivity.objects.create(opportunity=opportunity, subject="Call")
    api_client.force_authenticate(owner)

    response = api_client.get(f"{_detail(opportunity.pk)}activities/")

    assert response.status_code == 200
    assert len(response.data) == 1


def test_create_activity_action_stamps_author(api_client, opportunity, owner):
    api_client.force_authenticate(owner)

    response = api_client.post(
        f"{_detail(opportunity.pk)}activities/",
        {"activity_type": "CALL", "subject": "Intro call"},
    )

    assert response.status_code == 201
    activity = OpportunityActivity.objects.get(pk=response.data["id"])
    assert activity.subject == "Intro call"
    assert activity.created_by_id == owner.id


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------


def test_search_by_title(api_client, super_admin, customer):
    Opportunity.objects.create(customer=customer, title="Rocket Launch Deal")
    Opportunity.objects.create(customer=customer, title="Other Deal")
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL, {"search": "Rocket"})

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"Rocket Launch Deal"}


def test_search_by_customer_name(api_client, super_admin, organization):
    from apps.crm.models import Customer

    acme = Customer.objects.create(organization=organization, name="Acme Rockets", slug="acme-rockets-2")
    globex = Customer.objects.create(organization=organization, name="Globex", slug="globex-2")
    Opportunity.objects.create(customer=acme, title="Deal A")
    Opportunity.objects.create(customer=globex, title="Deal B")
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL, {"search": "Rockets"})

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"Deal A"}


def test_search_by_description(api_client, super_admin, customer):
    Opportunity.objects.create(customer=customer, title="A", description="mentions unicorn startup")
    Opportunity.objects.create(customer=customer, title="B", description="nothing special")
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL, {"search": "unicorn"})

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"A"}


# --------------------------------------------------------------------------
# Filtering
# --------------------------------------------------------------------------


def test_filter_by_stage(api_client, super_admin, customer):
    Opportunity.objects.create(customer=customer, title="A", stage=Opportunity.Stage.PROPOSAL)
    Opportunity.objects.create(customer=customer, title="B", stage=Opportunity.Stage.NEGOTIATION)
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL, {"stage": "PROPOSAL"})

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"A"}


def test_filter_by_closed_and_won(api_client, super_admin, customer):
    Opportunity.objects.create(customer=customer, title="Open")
    Opportunity.objects.create(customer=customer, title="Won", is_closed=True, is_won=True)
    Opportunity.objects.create(customer=customer, title="Lost", is_closed=True, is_won=False)
    api_client.force_authenticate(super_admin)

    closed_response = api_client.get(OPPS_URL, {"closed": "true"})
    won_response = api_client.get(OPPS_URL, {"won": "true"})

    assert {r["title"] for r in closed_response.data["results"]} == {"Won", "Lost"}
    assert {r["title"] for r in won_response.data["results"]} == {"Won"}


def test_filter_by_value_range(api_client, super_admin, customer):
    Opportunity.objects.create(customer=customer, title="Small", value="500.00")
    Opportunity.objects.create(customer=customer, title="Big", value="50000.00")
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL, {"value_min": "10000"})

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"Big"}


def test_filter_by_expected_close_date_range(api_client, super_admin, customer):
    Opportunity.objects.create(customer=customer, title="Early", expected_close_date="2026-01-15")
    Opportunity.objects.create(customer=customer, title="Late", expected_close_date="2026-06-15")
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL, {"expected_close_date_to": "2026-03-01"})

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"Early"}


def test_filter_by_owner_and_customer(api_client, super_admin, customer, employee, other_employee):
    Opportunity.objects.create(customer=customer, title="Mine", owner=employee)
    Opportunity.objects.create(customer=customer, title="Theirs", owner=other_employee)
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL, {"owner": employee.id})

    titles = {row["title"] for row in response.data["results"]}
    assert titles == {"Mine"}


# --------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------


def test_order_by_value(api_client, super_admin, customer):
    Opportunity.objects.create(customer=customer, title="Small", value="100.00")
    Opportunity.objects.create(customer=customer, title="Big", value="9000.00")
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL, {"ordering": "value"})

    titles = [row["title"] for row in response.data["results"]]
    assert titles == ["Small", "Big"]


def test_order_by_title(api_client, super_admin, customer):
    Opportunity.objects.create(customer=customer, title="Zebra Deal")
    Opportunity.objects.create(customer=customer, title="Alpha Deal")
    api_client.force_authenticate(super_admin)

    response = api_client.get(OPPS_URL, {"ordering": "title"})

    titles = [row["title"] for row in response.data["results"]]
    assert titles == ["Alpha Deal", "Zebra Deal"]
