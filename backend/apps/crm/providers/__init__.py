"""Staff-management pass: inbound data-source providers for CRM imports.

Mirrors ``apps.communications.providers``' established shape — one module
per external provider, credentials read from environment variables only,
never hardcoded, never returned in an API response, and never required
for the backend to start, run ``manage.py check``, or migrate.

Today: ``google_sheets``.
"""
