"""Staff-management pass: lead assignment authorization + the assignment
filters that back the Super Admin's Lead Assignment panel.

Covers the two independent checks ``services.assign_leads()`` makes (may
the caller assign to this target; is every lead already in the caller's
own scope) plus the role-matching and reassignment rules.
"""
import pytest

from apps.crm.models import Lead
from apps.crm.services import LeadAssignmentNotAllowed, assign_leads

ASSIGN_URL = "/api/v1/crm/leads/assign/"


@pytest.fixture
def unassigned_lead(db):
    return Lead.objects.create(company_name="Initech", contact_name="Peter G")


@pytest.fixture
def employee_lead(db, employee):
    return Lead.objects.create(company_name="Hooli", contact_name="Gavin B", owner=employee)


@pytest.fixture
def other_lead(db, other_employee):
    return Lead.objects.create(company_name="Pied Piper", contact_name="Richard H", owner=other_employee)


# --------------------------------------------------------------------------
# Service-level authorization
# --------------------------------------------------------------------------


def test_super_admin_can_assign_any_lead_to_an_employee(super_admin, employee, unassigned_lead):
    leads = assign_leads(super_admin, [unassigned_lead.pk], "employee", employee)

    assert [lead.owner_id for lead in leads] == [employee.pk]
    unassigned_lead.refresh_from_db()
    assert unassigned_lead.owner_id == employee.pk


def test_super_admin_can_assign_a_lead_to_a_manager(super_admin, manager, unassigned_lead):
    assign_leads(super_admin, [unassigned_lead.pk], "manager", manager)

    unassigned_lead.refresh_from_db()
    assert unassigned_lead.owner_id == manager.pk


def test_super_admin_can_reassign_an_already_assigned_lead(super_admin, employee, other_employee, employee_lead):
    assign_leads(super_admin, [employee_lead.pk], "employee", other_employee)

    employee_lead.refresh_from_db()
    assert employee_lead.owner_id == other_employee.pk


def test_employee_can_never_assign_leads(employee, other_employee, employee_lead):
    with pytest.raises(LeadAssignmentNotAllowed):
        assign_leads(employee, [employee_lead.pk], "employee", other_employee)


def test_target_role_must_match_target_type(super_admin, employee, unassigned_lead):
    with pytest.raises(LeadAssignmentNotAllowed):
        assign_leads(super_admin, [unassigned_lead.pk], "manager", employee)


def test_cannot_assign_to_a_deactivated_account(super_admin, employee, unassigned_lead):
    employee.is_active = False
    employee.save(update_fields=["is_active"])

    with pytest.raises(LeadAssignmentNotAllowed):
        assign_leads(super_admin, [unassigned_lead.pk], "employee", employee)


def test_manager_may_assign_only_within_their_own_scope(manager, employee, other_employee, managed_team):
    lead = Lead.objects.create(company_name="Umbrella", contact_name="Alice", owner=manager)

    assign_leads(manager, [lead.pk], "employee", employee)
    lead.refresh_from_db()
    assert lead.owner_id == employee.pk

    with pytest.raises(LeadAssignmentNotAllowed):
        assign_leads(manager, [lead.pk], "employee", other_employee)


def test_manager_cannot_assign_a_lead_outside_their_scope(manager, employee, other_lead, managed_team):
    """The lead itself must already be visible to the caller — an
    out-of-scope lead id is reported as not found, never silently assigned.
    """
    with pytest.raises(Lead.DoesNotExist):
        assign_leads(manager, [other_lead.pk], "employee", employee)


def test_empty_lead_ids_is_rejected(super_admin, employee):
    with pytest.raises(LeadAssignmentNotAllowed):
        assign_leads(super_admin, [], "employee", employee)


# --------------------------------------------------------------------------
# API surface
# --------------------------------------------------------------------------


def test_assign_endpoint_returns_updated_leads(api_client, super_admin, employee, unassigned_lead):
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        ASSIGN_URL,
        {"lead_ids": [unassigned_lead.pk], "target_type": "employee", "target_user_id": employee.pk},
        format="json",
    )

    assert response.status_code == 200
    assert response.data[0]["owner"] == employee.pk


def test_assign_endpoint_forbids_employees(api_client, employee, other_employee, employee_lead):
    api_client.force_authenticate(employee)

    response = api_client.post(
        ASSIGN_URL,
        {"lead_ids": [employee_lead.pk], "target_type": "employee", "target_user_id": other_employee.pk},
        format="json",
    )

    assert response.status_code == 403


def test_assign_endpoint_404s_for_an_out_of_scope_lead(api_client, manager, employee, other_lead, managed_team):
    api_client.force_authenticate(manager)

    response = api_client.post(
        ASSIGN_URL,
        {"lead_ids": [other_lead.pk], "target_type": "employee", "target_user_id": employee.pk},
        format="json",
    )

    assert response.status_code == 404


def test_assign_endpoint_validates_the_body(api_client, super_admin, employee):
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        ASSIGN_URL, {"lead_ids": [], "target_type": "employee", "target_user_id": employee.pk}, format="json"
    )

    assert response.status_code == 400


# --------------------------------------------------------------------------
# Assignment-state filters
# --------------------------------------------------------------------------


def test_unassigned_filter(api_client, super_admin, unassigned_lead, employee_lead):
    api_client.force_authenticate(super_admin)

    response = api_client.get("/api/v1/crm/leads/?unassigned=true")

    assert response.status_code == 200
    returned = {row["id"] for row in response.data["results"]}
    assert unassigned_lead.pk in returned
    assert employee_lead.pk not in returned


def test_owner_role_filter(api_client, super_admin, manager, employee, employee_lead):
    manager_lead = Lead.objects.create(company_name="Cyberdyne", contact_name="Miles D", owner=manager)
    api_client.force_authenticate(super_admin)

    response = api_client.get("/api/v1/crm/leads/?owner_role=MANAGER")

    returned = {row["id"] for row in response.data["results"]}
    assert manager_lead.pk in returned
    assert employee_lead.pk not in returned


def test_created_date_filters(api_client, super_admin, unassigned_lead):
    api_client.force_authenticate(super_admin)
    today = unassigned_lead.created_at.date().isoformat()

    response = api_client.get(f"/api/v1/crm/leads/?created_from={today}&created_to={today}")

    assert response.status_code == 200
    assert unassigned_lead.pk in {row["id"] for row in response.data["results"]}


# --------------------------------------------------------------------------
# Export / import are never available to an Employee
# --------------------------------------------------------------------------


def test_employee_cannot_export_leads(api_client, employee, employee_lead):
    api_client.force_authenticate(employee)

    assert api_client.get("/api/v1/crm/leads/export/?export_format=csv").status_code == 403


def test_employee_cannot_import_leads(api_client, employee):
    from django.core.files.uploadedfile import SimpleUploadedFile

    api_client.force_authenticate(employee)
    upload = SimpleUploadedFile("leads.csv", b"company_name,contact_name\nAcme,Jane\n", content_type="text/csv")

    response = api_client.post("/api/v1/crm/leads/import/", {"file": upload}, format="multipart")

    assert response.status_code == 403
    assert not Lead.objects.filter(company_name="Acme").exists()


def test_employee_cannot_preview_an_import(api_client, employee):
    api_client.force_authenticate(employee)

    assert api_client.post("/api/v1/crm/leads/import-preview/", {}, format="multipart").status_code == 403


def test_employee_cannot_use_the_google_sheet_import(api_client, employee):
    api_client.force_authenticate(employee)

    response = api_client.post(
        "/api/v1/crm/leads/import-google-sheet/", {"spreadsheet_id": "abc"}, format="json"
    )

    assert response.status_code == 403


def test_manager_can_still_export_within_their_scope(api_client, manager, employee, employee_lead, managed_team):
    api_client.force_authenticate(manager)

    response = api_client.get("/api/v1/crm/leads/export/?export_format=csv")

    assert response.status_code == 200
    assert b"Hooli" in response.content


def test_super_admin_can_export(api_client, super_admin, employee_lead):
    api_client.force_authenticate(super_admin)

    assert api_client.get("/api/v1/crm/leads/export/?export_format=csv").status_code == 200
