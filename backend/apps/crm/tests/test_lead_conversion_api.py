"""The lead -> customer conversion ENDPOINT.

``services.convert_lead()`` has existed and been unit-tested since CP9, but
was never exposed over HTTP — the UI offered a "Convert Lead" action that no
API could actually perform. These tests cover the endpoint that closes that
gap: ``POST /api/v1/crm/leads/<id>/convert/``.

The emphasis is deliberately on AUTHORIZATION and IDEMPOTENCY rather than on
re-testing the conversion mechanics themselves (test_services.py already
owns those): one shared endpoint must behave correctly for all three roles,
must not widen anyone's reach, and must never produce two customers from one
lead.
"""
import pytest

from apps.crm.models import Customer, Lead

LEADS_URL = "/api/v1/crm/leads/"


def _convert_url(lead):
    return f"{LEADS_URL}{lead.pk}/convert/"


@pytest.fixture
def employee_lead(db, employee):
    return Lead.objects.create(
        company_name="Initech", contact_name="Peter Gibbons", email="peter@initech.test", owner=employee
    )


@pytest.fixture
def unrelated_lead(db, other_employee):
    return Lead.objects.create(
        company_name="Umbrella", contact_name="Ada Wong", email="ada@umbrella.test", owner=other_employee
    )


# --------------------------------------------------------------------------
# The happy path, for each authorized role
# --------------------------------------------------------------------------


def test_employee_can_convert_their_own_lead(api_client, employee, employee_lead, organization):
    api_client.force_authenticate(employee)

    response = api_client.post(_convert_url(employee_lead), {}, format="json")

    assert response.status_code == 201
    employee_lead.refresh_from_db()
    assert employee_lead.status == Lead.Status.CONVERTED
    assert employee_lead.converted_customer is not None
    # The response describes the REAL created row, not a hopeful echo.
    assert response.data["id"] == employee_lead.converted_customer_id
    assert Customer.objects.filter(pk=response.data["id"]).exists()


def test_manager_can_convert_a_lead_in_their_scope(
    api_client, manager, employee, employee_lead, managed_team, organization
):
    api_client.force_authenticate(manager)

    response = api_client.post(_convert_url(employee_lead), {}, format="json")

    assert response.status_code == 201
    employee_lead.refresh_from_db()
    assert employee_lead.status == Lead.Status.CONVERTED


def test_super_admin_can_convert_any_lead(api_client, super_admin, employee_lead, organization):
    api_client.force_authenticate(super_admin)

    response = api_client.post(_convert_url(employee_lead), {}, format="json")

    assert response.status_code == 201
    employee_lead.refresh_from_db()
    assert employee_lead.status == Lead.Status.CONVERTED


def test_conversion_preserves_the_leads_contact_details(api_client, employee, employee_lead, organization):
    api_client.force_authenticate(employee)

    response = api_client.post(_convert_url(employee_lead), {}, format="json")

    customer = Customer.objects.get(pk=response.data["id"])
    assert customer.name == employee_lead.company_name
    assert customer.email == employee_lead.email
    # Ownership carries over, so the converting employee does not lose the
    # record they just converted.
    assert customer.owner_id == employee_lead.owner_id


# --------------------------------------------------------------------------
# Authorization — the endpoint must not widen anyone's reach
# --------------------------------------------------------------------------


def test_employee_cannot_convert_someone_elses_lead(api_client, employee, unrelated_lead, organization):
    api_client.force_authenticate(employee)

    response = api_client.post(_convert_url(unrelated_lead), {}, format="json")

    # 404, not 403 — out-of-scope rows are invisible, they don't announce
    # themselves. Same rule as every other detail route on this viewset.
    assert response.status_code == 404
    unrelated_lead.refresh_from_db()
    assert unrelated_lead.converted_customer is None
    assert unrelated_lead.status != Lead.Status.CONVERTED


def test_manager_cannot_convert_a_lead_outside_their_team(api_client, manager, unrelated_lead, organization):
    api_client.force_authenticate(manager)

    response = api_client.post(_convert_url(unrelated_lead), {}, format="json")

    assert response.status_code == 404
    unrelated_lead.refresh_from_db()
    assert unrelated_lead.converted_customer is None


def test_anonymous_cannot_convert(api_client, employee_lead, organization):
    response = api_client.post(_convert_url(employee_lead), {}, format="json")

    assert response.status_code in (401, 403)
    employee_lead.refresh_from_db()
    assert employee_lead.converted_customer is None


# --------------------------------------------------------------------------
# Integrity — a lead converts exactly once
# --------------------------------------------------------------------------


def test_converting_twice_is_rejected_and_creates_no_second_customer(
    api_client, employee, employee_lead, organization
):
    api_client.force_authenticate(employee)
    first = api_client.post(_convert_url(employee_lead), {}, format="json")
    assert first.status_code == 201

    second = api_client.post(_convert_url(employee_lead), {}, format="json")

    assert second.status_code == 400
    assert "already been converted" in str(second.data["detail"])
    employee_lead.refresh_from_db()
    assert Customer.objects.filter(pk=employee_lead.converted_customer_id).count() == 1
    assert Customer.objects.count() == 1


def test_a_second_role_cannot_reconvert_an_already_converted_lead(
    api_client, employee, super_admin, employee_lead, organization
):
    api_client.force_authenticate(employee)
    api_client.post(_convert_url(employee_lead), {}, format="json")

    api_client.force_authenticate(super_admin)
    response = api_client.post(_convert_url(employee_lead), {}, format="json")

    assert response.status_code == 400
    assert Customer.objects.count() == 1


def test_an_invalid_organization_is_rejected(api_client, employee, employee_lead, organization):
    api_client.force_authenticate(employee)

    response = api_client.post(_convert_url(employee_lead), {"organization": 999999}, format="json")

    assert response.status_code == 400
    assert "organization" in response.data
    employee_lead.refresh_from_db()
    assert employee_lead.converted_customer is None


def test_conversion_reports_honestly_when_no_organization_exists(api_client, employee, employee_lead):
    """No organization is a real, explainable failure — never a fake success."""
    api_client.force_authenticate(employee)

    response = api_client.post(_convert_url(employee_lead), {}, format="json")

    assert response.status_code == 400
    assert "organization" in str(response.data["detail"]).lower()
    employee_lead.refresh_from_db()
    assert employee_lead.converted_customer is None
    assert employee_lead.status != Lead.Status.CONVERTED
