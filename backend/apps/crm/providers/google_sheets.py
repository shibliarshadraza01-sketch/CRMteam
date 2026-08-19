"""Google Sheets import adapter — integration-ready, credential-optional.

Why a dedicated adapter rather than an ``apps.integrations.Integration``
row: that framework models an integration's IDENTITY plus the API keys and
webhook endpoints it owns (see ``apps/integrations/models.py``) — it has
no credential/config storage of its own and nothing about pulling rows out
of a spreadsheet. A bulk spreadsheet READ is the same shape as this
project's existing outbound provider clients (``apps.communications.providers``):
a small class over one external API, env-driven credentials, one
provider-specific exception. So this follows that pattern instead, and an
``Integration`` row can still be created alongside it purely as the
human-visible registry entry if a Super Admin wants one.

Hard rules honored here (see the deployment-readiness requirements):

- **Startup never depends on credentials.** Nothing is read at import
  time; ``GOOGLE_SHEETS_API_KEY``/``GOOGLE_SHEETS_CREDENTIALS_JSON`` are
  read inside ``__init__``. Importing this module with no credentials set
  is fine, and ``manage.py check``/``migrate``/``runserver`` are entirely
  unaffected.
- **Never fake success.** With no credentials configured, ``fetch_rows()``
  raises ``GoogleSheetsNotConfigured`` — the API surfaces that as a clear
  503 "not configured", never a fabricated successful import.
- **A local dev provider exists, and is opt-in and clearly labelled.**
  Set ``GOOGLE_SHEETS_PROVIDER=mock`` plus ``GOOGLE_SHEETS_MOCK_ROWS``
  (a JSON array of row objects) to exercise the whole
  source -> validate -> preview -> confirm pipeline locally. The mock is
  never selected implicitly: the default provider is the real one, which
  fails closed.

The rows this returns are the SAME plain dicts
``apps.crm.imports.parse_rows_from_file()`` produces, so both the preview
and the confirm step reuse the existing ``import_leads()`` pipeline
unchanged rather than growing a parallel one.
"""
import json
import os

DEFAULT_API_URL = "https://sheets.googleapis.com/v4/spreadsheets"
REQUEST_TIMEOUT_SECONDS = 15


class GoogleSheetsError(Exception):
    """Any failure talking to the Google Sheets API."""


class GoogleSheetsNotConfigured(GoogleSheetsError):
    """No Google Sheets credentials are configured.

    Its own subclass (not a bare ``GoogleSheetsError``) so the API layer
    can answer "this integration isn't set up yet" (503) differently from
    "the call was attempted and failed" (502) — and so neither is ever
    mistaken for a successful import.
    """


class BaseGoogleSheetsProvider:
    """Interface: return a list of plain row dicts for a spreadsheet."""

    name = "base"

    def fetch_rows(self, spreadsheet_id, sheet_range):  # pragma: no cover - interface
        raise NotImplementedError


class GoogleSheetsAPIProvider(BaseGoogleSheetsProvider):
    """The real client. Reads an API key from the environment at
    construction time; raises ``GoogleSheetsNotConfigured`` when absent
    rather than pretending to work.
    """

    name = "google_sheets_api"

    def __init__(self, api_key=None, api_url=None):
        self.api_key = api_key if api_key is not None else os.environ.get("GOOGLE_SHEETS_API_KEY", "")
        self.api_url = (
            api_url if api_url is not None else os.environ.get("GOOGLE_SHEETS_API_URL", DEFAULT_API_URL)
        ).rstrip("/")

    def fetch_rows(self, spreadsheet_id, sheet_range):
        if not self.api_key:
            raise GoogleSheetsNotConfigured(
                "Google Sheets is not configured on this deployment "
                "(set GOOGLE_SHEETS_API_KEY to enable spreadsheet imports)."
            )
        if not spreadsheet_id:
            raise GoogleSheetsError("spreadsheet_id is required.")

        import requests  # imported lazily so this module stays import-safe anywhere

        url = f"{self.api_url}/{spreadsheet_id}/values/{sheet_range or 'Sheet1'}"
        try:
            response = requests.get(url, params={"key": self.api_key}, timeout=REQUEST_TIMEOUT_SECONDS)
        except Exception as exc:  # requests.RequestException and friends
            raise GoogleSheetsError(f"Could not reach the Google Sheets API: {exc}") from exc

        if not response.ok:
            raise GoogleSheetsError(
                f"Google Sheets API rejected the request ({response.status_code})."
            )
        try:
            values = response.json().get("values", [])
        except ValueError as exc:
            raise GoogleSheetsError("Google Sheets API returned a non-JSON response.") from exc
        return rows_from_values(values)


class MockGoogleSheetsProvider(BaseGoogleSheetsProvider):
    """Local/dev provider — explicitly opt-in via
    ``GOOGLE_SHEETS_PROVIDER=mock``. Returns rows from
    ``GOOGLE_SHEETS_MOCK_ROWS`` (JSON array of objects). Never selected by
    default, and clearly named so a mocked import can never be mistaken
    for a real one.
    """

    name = "mock"

    def fetch_rows(self, spreadsheet_id, sheet_range):
        raw = os.environ.get("GOOGLE_SHEETS_MOCK_ROWS", "[]")
        try:
            rows = json.loads(raw)
        except ValueError as exc:
            raise GoogleSheetsError("GOOGLE_SHEETS_MOCK_ROWS is not valid JSON.") from exc
        if not isinstance(rows, list):
            raise GoogleSheetsError("GOOGLE_SHEETS_MOCK_ROWS must be a JSON array of row objects.")
        return [{str(k): ("" if v is None else str(v)) for k, v in row.items()} for row in rows]


PROVIDERS = {
    GoogleSheetsAPIProvider.name: GoogleSheetsAPIProvider,
    MockGoogleSheetsProvider.name: MockGoogleSheetsProvider,
    "google_sheets": GoogleSheetsAPIProvider,
}

DEFAULT_PROVIDER_NAME = GoogleSheetsAPIProvider.name


def rows_from_values(values):
    """Convert the Sheets API's row-major ``values`` array (first row =
    header) into the same list-of-dicts shape
    ``apps.crm.imports.parse_rows_from_file()`` returns.
    """
    if not values:
        return []
    header = [str(cell).strip() if cell is not None else "" for cell in values[0]]
    rows = []
    for raw_row in values[1:]:
        if not raw_row or all(cell in (None, "") for cell in raw_row):
            continue
        row = {}
        for index, column in enumerate(header):
            if not column:
                continue
            value = raw_row[index] if index < len(raw_row) else ""
            row[column] = "" if value is None else str(value).strip()
        rows.append(row)
    return rows


def get_provider():
    """Resolve the configured provider at CALL time (never import time).
    An unknown name degrades to the real API provider, which fails closed
    with ``GoogleSheetsNotConfigured`` — never to the mock.
    """
    name = os.environ.get("GOOGLE_SHEETS_PROVIDER", DEFAULT_PROVIDER_NAME)
    provider_class = PROVIDERS.get(name, PROVIDERS[DEFAULT_PROVIDER_NAME])
    return provider_class()


def is_configured():
    """Whether an import could currently succeed. Cheap, side-effect-free,
    and safe to call with nothing configured — used by the status endpoint
    so a UI can disable the button instead of discovering a 503.
    """
    provider = get_provider()
    if isinstance(provider, MockGoogleSheetsProvider):
        return True
    return bool(getattr(provider, "api_key", ""))


def provider_status():
    """Status payload for the API — never includes any credential value."""
    provider = get_provider()
    return {
        "provider": provider.name,
        "configured": is_configured(),
        "is_mock": isinstance(provider, MockGoogleSheetsProvider),
    }


def fetch_rows(spreadsheet_id, sheet_range=None):
    """Fetch rows via the configured provider. Raises
    ``GoogleSheetsNotConfigured`` when credentials are absent.
    """
    return get_provider().fetch_rows(spreadsheet_id, sheet_range)


__all__ = [
    "GoogleSheetsError",
    "GoogleSheetsNotConfigured",
    "BaseGoogleSheetsProvider",
    "GoogleSheetsAPIProvider",
    "MockGoogleSheetsProvider",
    "PROVIDERS",
    "rows_from_values",
    "get_provider",
    "is_configured",
    "provider_status",
    "fetch_rows",
]
