"""Staff-management pass: the Google Sheets import adapter and the
source -> adapter -> validation -> preview -> confirm -> CRM records flow.

The single most important assertion here: with NO credentials configured
the backend still imports, starts, and answers — it reports "not
configured" rather than fabricating a successful external call.
"""
import json

import pytest

from apps.crm.imports import preview_leads
from apps.crm.models import Lead
from apps.crm.providers import google_sheets

PREVIEW_URL = "/api/v1/crm/leads/import-preview/"
SHEET_URL = "/api/v1/crm/leads/import-google-sheet/"
STATUS_URL = "/api/v1/crm/leads/google-sheet-status/"

SAMPLE_ROWS = [
    {"company_name": "Acme", "contact_name": "Wile E", "email": "wile@acme.test", "source": "Cold Call"},
    {"company_name": "", "contact_name": "Missing Company"},
]


# --------------------------------------------------------------------------
# Adapter: never blocks, never fakes
# --------------------------------------------------------------------------


def test_importing_the_module_needs_no_credentials():
    """Nothing is read at import time — that is what keeps ``manage.py
    check``/``migrate``/startup independent of this integration.
    """
    assert google_sheets.DEFAULT_API_URL.startswith("https://")


def test_fetch_without_credentials_raises_not_configured(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEETS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SHEETS_PROVIDER", raising=False)

    with pytest.raises(google_sheets.GoogleSheetsNotConfigured):
        google_sheets.fetch_rows("some-sheet-id")


def test_status_reports_unconfigured_without_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEETS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SHEETS_PROVIDER", raising=False)

    status = google_sheets.provider_status()

    assert status["configured"] is False
    assert status["is_mock"] is False


def test_unknown_provider_name_falls_back_to_the_real_one_not_the_mock(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_PROVIDER", "made-up")
    monkeypatch.delenv("GOOGLE_SHEETS_API_KEY", raising=False)

    provider = google_sheets.get_provider()

    assert isinstance(provider, google_sheets.GoogleSheetsAPIProvider)


def test_mock_provider_is_explicitly_opt_in(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_PROVIDER", "mock")
    monkeypatch.setenv("GOOGLE_SHEETS_MOCK_ROWS", json.dumps(SAMPLE_ROWS))

    rows = google_sheets.fetch_rows("ignored")

    assert rows[0]["company_name"] == "Acme"


def test_rows_from_values_maps_the_header_row():
    values = [["company_name", "contact_name"], ["Acme", "Wile E"], [None, None]]

    rows = google_sheets.rows_from_values(values)

    assert rows == [{"company_name": "Acme", "contact_name": "Wile E"}]


# --------------------------------------------------------------------------
# Preview stage: validates, writes nothing
# --------------------------------------------------------------------------


def test_preview_validates_without_creating_anything(db):
    result = preview_leads(SAMPLE_ROWS)

    assert result["total"] == 2
    assert result["valid"] == 1
    assert result["invalid"] == 1
    assert result["errors"][0]["row"] == 2
    assert Lead.objects.count() == 0


def test_preview_sample_shows_normalized_values(db):
    sample = preview_leads(SAMPLE_ROWS)["sample"][0]

    assert sample["source"] == Lead.Source.COLD_CALL
    assert sample["status"] == Lead.Status.NEW


def test_import_preview_endpoint_requires_a_file(api_client, super_admin):
    api_client.force_authenticate(super_admin)

    response = api_client.post(PREVIEW_URL, {}, format="multipart")

    assert response.status_code == 400


def test_import_preview_endpoint_writes_nothing(api_client, super_admin):
    from django.core.files.uploadedfile import SimpleUploadedFile

    csv_bytes = b"company_name,contact_name\nAcme,Wile E\n"
    api_client.force_authenticate(super_admin)

    response = api_client.post(
        PREVIEW_URL,
        {"file": SimpleUploadedFile("leads.csv", csv_bytes, content_type="text/csv")},
        format="multipart",
    )

    assert response.status_code == 200
    assert response.data["valid"] == 1
    assert Lead.objects.count() == 0


# --------------------------------------------------------------------------
# Google-Sheets-sourced import endpoint
# --------------------------------------------------------------------------


def test_sheet_status_endpoint(api_client, super_admin, monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEETS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SHEETS_PROVIDER", raising=False)
    api_client.force_authenticate(super_admin)

    response = api_client.get(STATUS_URL)

    assert response.status_code == 200
    assert response.data["configured"] is False


def test_sheet_import_returns_503_when_unconfigured(api_client, super_admin, monkeypatch):
    """Never a fabricated success — an unconfigured integration says so."""
    monkeypatch.delenv("GOOGLE_SHEETS_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_SHEETS_PROVIDER", raising=False)
    api_client.force_authenticate(super_admin)

    response = api_client.post(SHEET_URL, {"spreadsheet_id": "abc"}, format="json")

    assert response.status_code == 503
    assert response.data["configured"] is False
    assert Lead.objects.count() == 0


def test_sheet_import_previews_by_default(api_client, super_admin, monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_PROVIDER", "mock")
    monkeypatch.setenv("GOOGLE_SHEETS_MOCK_ROWS", json.dumps(SAMPLE_ROWS))
    api_client.force_authenticate(super_admin)

    response = api_client.post(SHEET_URL, {"spreadsheet_id": "abc"}, format="json")

    assert response.status_code == 200
    assert response.data["stage"] == "preview"
    assert response.data["valid"] == 1
    assert Lead.objects.count() == 0


def test_sheet_import_creates_records_on_confirm(api_client, super_admin, monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_PROVIDER", "mock")
    monkeypatch.setenv("GOOGLE_SHEETS_MOCK_ROWS", json.dumps(SAMPLE_ROWS))
    api_client.force_authenticate(super_admin)

    response = api_client.post(SHEET_URL, {"spreadsheet_id": "abc", "confirm": True}, format="json")

    assert response.status_code == 200
    assert response.data["stage"] == "imported"
    assert response.data["created"] == 1
    assert response.data["failed"] == 1
    lead = Lead.objects.get(company_name="Acme")
    assert lead.owner_id == super_admin.pk


def test_sheet_import_requires_a_spreadsheet_id(api_client, super_admin):
    api_client.force_authenticate(super_admin)

    response = api_client.post(SHEET_URL, {}, format="json")

    assert response.status_code == 400
