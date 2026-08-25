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


# --------------------------------------------------------------------------
# Spreadsheet-ID parsing and range encoding
#
# Two real implementation bugs, both reachable WITHOUT any credentials:
# a pasted sheet URL was used verbatim as the document id, and the sheet
# range was interpolated into the request path unencoded even though a
# perfectly ordinary range ("Sheet1!A1:F500") contains "!".
# --------------------------------------------------------------------------


def test_a_bare_spreadsheet_id_is_accepted_unchanged():
    assert google_sheets.extract_spreadsheet_id("1AbC_dEf-123") == "1AbC_dEf-123"


def test_a_pasted_sheet_url_yields_the_document_id():
    url = "https://docs.google.com/spreadsheets/d/1AbC_dEf-123/edit#gid=0"

    assert google_sheets.extract_spreadsheet_id(url) == "1AbC_dEf-123"


def test_a_sheet_url_without_a_fragment_also_works():
    url = "https://docs.google.com/spreadsheets/d/1AbC_dEf-123/edit"

    assert google_sheets.extract_spreadsheet_id(url) == "1AbC_dEf-123"


def test_surrounding_whitespace_is_ignored():
    assert google_sheets.extract_spreadsheet_id("  1AbC_dEf-123  ") == "1AbC_dEf-123"


def test_an_empty_spreadsheet_id_is_rejected():
    with pytest.raises(google_sheets.GoogleSheetsError):
        google_sheets.extract_spreadsheet_id("")


def test_an_unparseable_value_is_rejected_locally_not_sent_upstream():
    with pytest.raises(google_sheets.GoogleSheetsError) as excinfo:
        google_sheets.extract_spreadsheet_id("https://example.com/not-a-sheet")

    assert "spreadsheet ID" in str(excinfo.value)


def _capture_request_url(monkeypatch):
    """Run the real provider against a stubbed `requests.get`, returning the
    URL it would have called. No network, no credentials beyond a fake key.
    """
    import sys
    import types

    captured = {}

    class _FakeResponse:
        ok = True
        status_code = 200

        def json(self):
            return {"values": [["company_name"], ["Acme"]]}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse()

    fake_requests = types.ModuleType("requests")
    fake_requests.get = fake_get
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    return captured


def test_a_pasted_url_produces_a_correct_api_path(monkeypatch):
    captured = _capture_request_url(monkeypatch)
    provider = google_sheets.GoogleSheetsAPIProvider(api_key="test-key")

    provider.fetch_rows("https://docs.google.com/spreadsheets/d/1AbC_dEf-123/edit#gid=0", None)

    # The document id, not the whole URL, lands in the path.
    assert "/1AbC_dEf-123/values/" in captured["url"]
    assert "docs.google.com" not in captured["url"].replace(
        google_sheets.DEFAULT_API_URL, ""
    )


def test_a_range_containing_an_exclamation_mark_is_percent_encoded(monkeypatch):
    captured = _capture_request_url(monkeypatch)
    provider = google_sheets.GoogleSheetsAPIProvider(api_key="test-key")

    provider.fetch_rows("1AbC_dEf-123", "Sheet1!A1:F500")

    assert "Sheet1%21A1%3AF500" in captured["url"]
    assert "!" not in captured["url"]


def test_a_tab_name_with_a_space_is_percent_encoded(monkeypatch):
    captured = _capture_request_url(monkeypatch)
    provider = google_sheets.GoogleSheetsAPIProvider(api_key="test-key")

    provider.fetch_rows("1AbC_dEf-123", "'My Leads'!A:G")

    assert " " not in captured["url"]
    assert "%20" in captured["url"]


def test_the_default_range_is_still_used_when_none_is_given(monkeypatch):
    captured = _capture_request_url(monkeypatch)
    provider = google_sheets.GoogleSheetsAPIProvider(api_key="test-key")

    provider.fetch_rows("1AbC_dEf-123", None)

    assert captured["url"].endswith("/values/Sheet1")


def test_the_api_key_travels_as_a_query_param_not_in_the_path(monkeypatch):
    captured = _capture_request_url(monkeypatch)
    provider = google_sheets.GoogleSheetsAPIProvider(api_key="test-key")

    provider.fetch_rows("1AbC_dEf-123", None)

    assert captured["params"] == {"key": "test-key"}
    assert "test-key" not in captured["url"]
