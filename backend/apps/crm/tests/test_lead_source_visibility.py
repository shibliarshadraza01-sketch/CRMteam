"""Staff-management pass: Lead Source is SUPER-ADMIN-ONLY.

A deliberately different, stricter rule from the existing contact-PII
masking (email/phone hidden from an Employee, still visible to a
Manager) — these tests assert BOTH rules hold simultaneously and neither
has been weakened into the other.
"""
import csv
import io

import pytest

from apps.crm.models import Lead

LIST_URL = "/api/v1/crm/leads/"


@pytest.fixture
def employee_lead(db, employee):
    return Lead.objects.create(
        company_name="Hooli",
        contact_name="Gavin B",
        email="gavin@hooli.test",
        phone="+15550001",
        source=Lead.Source.REFERRAL,
        owner=employee,
    )


def _row(response, lead_id):
    return next(row for row in response.data["results"] if row["id"] == lead_id)


def test_super_admin_sees_lead_source(api_client, super_admin, employee_lead):
    api_client.force_authenticate(super_admin)

    response = api_client.get(LIST_URL)

    assert _row(response, employee_lead.pk)["source"] == Lead.Source.REFERRAL


def test_manager_never_sees_lead_source(api_client, manager, employee, employee_lead, managed_team):
    api_client.force_authenticate(manager)

    response = api_client.get(LIST_URL)

    assert "source" not in _row(response, employee_lead.pk)


def test_employee_never_sees_lead_source(api_client, employee, employee_lead):
    api_client.force_authenticate(employee)

    response = api_client.get(LIST_URL)

    assert "source" not in _row(response, employee_lead.pk)


def test_manager_still_sees_contact_pii(api_client, manager, employee, employee_lead, managed_team):
    """The pre-existing PII rule is UNCHANGED: a Manager keeps full
    email/phone visibility. Only Lead Source changed for them.
    """
    api_client.force_authenticate(manager)

    row = _row(api_client.get(LIST_URL), employee_lead.pk)

    assert row["email"] == "gavin@hooli.test"
    assert row["phone"] == "+15550001"


def test_employee_still_has_contact_pii_masked(api_client, employee, employee_lead):
    api_client.force_authenticate(employee)

    row = _row(api_client.get(LIST_URL), employee_lead.pk)

    assert "email" not in row
    assert "phone" not in row


def test_retrieve_also_strips_source_for_a_manager(api_client, manager, employee, employee_lead, managed_team):
    api_client.force_authenticate(manager)

    response = api_client.get(f"{LIST_URL}{employee_lead.pk}/")

    assert response.status_code == 200
    assert "source" not in response.data


def test_source_filter_is_unavailable_below_super_admin(api_client, manager, employee, employee_lead, managed_team):
    """Filtering by source would let a Manager recover the hidden value one
    query at a time, so the filter is removed for them — the parameter is
    ignored rather than honored.
    """
    api_client.force_authenticate(manager)

    response = api_client.get(f"{LIST_URL}?source={Lead.Source.WEBSITE}")

    assert response.status_code == 200
    # WEBSITE does not match this lead's REFERRAL source; if the filter were
    # still active the lead would be excluded.
    assert employee_lead.pk in {row["id"] for row in response.data["results"]}


def test_source_filter_still_works_for_super_admin(api_client, super_admin, employee_lead):
    api_client.force_authenticate(super_admin)

    response = api_client.get(f"{LIST_URL}?source={Lead.Source.WEBSITE}")

    assert employee_lead.pk not in {row["id"] for row in response.data["results"]}


def test_export_omits_source_column_for_a_manager(api_client, manager, employee, employee_lead, managed_team):
    api_client.force_authenticate(manager)

    response = api_client.get(f"{LIST_URL}export/?export_format=csv")

    assert response.status_code == 200
    header = next(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert "source" not in header
    # PII columns are still there for a Manager — unchanged behavior.
    assert "email" in header


def test_export_includes_source_column_for_super_admin(api_client, super_admin, employee_lead):
    api_client.force_authenticate(super_admin)

    response = api_client.get(f"{LIST_URL}export/?export_format=csv")

    header = next(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert "source" in header
