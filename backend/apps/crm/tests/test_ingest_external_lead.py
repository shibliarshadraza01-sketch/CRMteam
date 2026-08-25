"""Final pre-production pass: regression tests for
``apps.crm.services.ingest_external_lead()`` — the generic, provider-
agnostic service function a FUTURE webhook/integration view will call for
Meta/Google Ads/WhatsApp/website-form leads. No actual integration exists
yet (see the function's own docstring); these tests exercise the service
function directly, the same way every other ``apps/crm/services.py``
function is tested in this file's sibling ``test_services.py``.
"""
import pytest

from apps.crm.models import Lead
from apps.crm.services import ExternalLeadIngestionError, ingest_external_lead

pytestmark = pytest.mark.django_db

VALID_KWARGS = dict(
    provider="meta",
    external_source_id="lead_12345",
    company_name="Acme Inc",
    contact_name="Jane Doe",
    email="jane@acme.example",
    phone="555-0100",
)


def test_first_ingestion_creates_a_lead():
    lead, created = ingest_external_lead(**VALID_KWARGS)

    assert created is True
    assert isinstance(lead, Lead)
    assert lead.external_source_id == "lead_12345"
    assert lead.company_name == "Acme Inc"
    assert lead.contact_name == "Jane Doe"
    assert lead.source_metadata["provider"] == "meta"
    # Known provider → mapped Source choice for the existing "Source"
    # filter/reporting UI; see EXTERNAL_LEAD_PROVIDER_SOURCE_MAP.
    assert lead.source == Lead.Source.ADVERTISEMENT


def test_repeated_ingestion_same_external_id_returns_same_lead_no_duplicate():
    first_lead, first_created = ingest_external_lead(**VALID_KWARGS)
    second_lead, second_created = ingest_external_lead(**VALID_KWARGS)

    assert first_created is True
    assert second_created is False
    assert second_lead.pk == first_lead.pk
    assert Lead.objects.filter(external_source_id="lead_12345").count() == 1


def test_repeated_ingestion_can_change_contact_fields_without_creating_new_row():
    # A webhook retry / re-sync may carry a corrected phone number etc for
    # the same external event — must still resolve to ONE lead.
    ingest_external_lead(**VALID_KWARGS)
    lead, created = ingest_external_lead(
        provider="meta",
        external_source_id="lead_12345",
        company_name="Acme Inc",
        contact_name="Jane Doe",
        email="jane@acme.example",
        phone="555-9999",
    )

    assert created is False
    assert Lead.objects.filter(external_source_id="lead_12345").count() == 1


def test_concurrent_duplicate_ingestion_resolves_to_one_lead(monkeypatch):
    """Exercises ``ingest_external_lead()``'s ``IntegrityError`` recovery
    path — the last-resort guarantee for when a genuine race (two
    concurrent requests for the same ``external_source_id``) slips past
    the ``select_for_update()`` check and both attempt the INSERT.

    A REAL two-connection/two-thread race against this project's test
    Postgres database was tried first and had to be abandoned: pytest-
    django's ``transaction=True`` (``TransactionTestCase``) mode — the
    only way to give two threads two independently-committing connections
    — FAILS at its own post-test ``flush()`` teardown in this environment
    with ``psycopg.errors.FeatureNotSupported: cannot truncate a table
    referenced in a foreign key constraint`` (``core_sampletimestamped``
    → ``accounts_user``), a pre-existing environment/schema limitation
    unrelated to this feature and out of scope to fix here (touching
    ``apps.core``'s test-only model FK setup is not part of "build the
    ingestion service layer"). Verified: the test's own two ingestion
    calls run and resolve to one row correctly (visible in the run's
    output) — only the unrelated teardown ``flush()`` errors.

    This deterministic version instead reproduces the exact race WINDOW,
    using the real database's real ``UniqueConstraint`` for the actual
    error (nothing about the ``IntegrityError`` itself is faked):

    1. The "concurrent winner" row is inserted FIRST, as an ordinary,
       already-committed row — standing in for the other request that got
       there first.
    2. ``services._lock_existing_lead_by_external_id()`` — the ONE small
       function ``ingest_external_lead()`` calls to do its
       ``select_for_update()`` existence check — is monkeypatched to
       return ``None`` exactly once, standing in for "our own check ran
       in the narrow window BEFORE the winner's row existed" (the
       precise race window two real concurrent requests could hit).
    3. ``ingest_external_lead()`` then proceeds to its real
       ``Lead.objects.create()`` call, which hits the REAL
       ``crm_lead_unique_external_source_id`` constraint against the
       winner row and raises a genuine ``django.db.IntegrityError`` — the
       exact exception ``ingest_external_lead()`` is built to catch.

    This is a faithful simulation of the race's DATABASE-level
    consequence (a real constraint violation on a real conflicting row),
    while staying deterministic and avoiding this environment's broken
    ``TransactionTestCase`` teardown.
    """
    from apps.crm import services as crm_services

    winner, _created = ingest_external_lead(
        provider="meta",
        external_source_id="race-id-1",
        company_name="Race Co (winner)",
        contact_name="Race Contact",
        email="race-winner@example.com",
        phone="555-2222",
    )

    original_lock = crm_services._lock_existing_lead_by_external_id
    call_count = {"n": 0}

    def fake_lock(external_source_id):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Simulate this request's own existence check having run
            # BEFORE the winner's row was actually committed.
            return None
        return original_lock(external_source_id)

    monkeypatch.setattr(crm_services, "_lock_existing_lead_by_external_id", fake_lock)

    lead, created = ingest_external_lead(
        provider="google_ads",
        external_source_id="race-id-1",
        company_name="Race Co (loser)",
        contact_name="Race Contact",
        email="race-loser@example.com",
        phone="555-1111",
    )

    assert created is False
    assert lead.pk == winner.pk
    assert Lead.objects.filter(external_source_id="race-id-1").count() == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"provider": ""},
        {"provider": "   "},
        {"external_source_id": ""},
        {"company_name": ""},
        {"contact_name": ""},
        {"email": "", "phone": ""},
    ],
)
def test_malformed_input_is_rejected_cleanly(overrides):
    kwargs = {**VALID_KWARGS, **overrides}

    with pytest.raises(ExternalLeadIngestionError):
        ingest_external_lead(**kwargs)

    # Nothing was created despite the raise.
    assert Lead.objects.count() == 0


def test_missing_external_source_id_is_rejected_not_silently_dropped():
    with pytest.raises(ExternalLeadIngestionError):
        ingest_external_lead(
            provider="meta",
            external_source_id="",
            company_name="Acme Inc",
            contact_name="Jane Doe",
            email="jane@acme.example",
        )


def test_two_different_providers_reusing_the_same_raw_id_collide_as_documented():
    # Known, documented limitation: the UniqueConstraint is on
    # external_source_id ALONE (not namespaced per provider), so two
    # different providers reusing the exact same raw id string collide —
    # the second provider's lead resolves to the FIRST provider's existing
    # row rather than creating a distinct one. This test locks in and
    # documents that current behavior (not a bug this pass introduces).
    first_lead, first_created = ingest_external_lead(
        provider="meta",
        external_source_id="1",
        company_name="Meta Co",
        contact_name="Meta Contact",
        email="meta-contact@example.com",
    )
    second_lead, second_created = ingest_external_lead(
        provider="google_ads",
        external_source_id="1",
        company_name="Google Co",
        contact_name="Google Contact",
        email="google-contact@example.com",
    )

    assert first_created is True
    assert second_created is False
    assert second_lead.pk == first_lead.pk
    # A caller who needs cross-provider isolation should namespace the id
    # itself (e.g. f"{provider}:{raw_id}") — see ingest_external_lead()'s
    # own docstring "Known limitation" section.


def test_contact_duplicate_without_external_id_is_reused_not_duplicated():
    # A lead entered by hand (no external_source_id) that matches the
    # incoming contact's email should be reused rather than creating a
    # second row for the same real person.
    from apps.crm.services import create_lead

    manual_lead = create_lead(company_name="Acme Inc", contact_name="Jane Doe", email="jane@acme.example")

    lead, created = ingest_external_lead(**VALID_KWARGS)

    assert created is False
    assert lead.pk == manual_lead.pk
    assert lead.external_source_id == "lead_12345"


def test_unknown_provider_defaults_to_other_source_and_is_preserved_in_metadata():
    lead, created = ingest_external_lead(
        provider="some_future_provider",
        external_source_id="future-1",
        company_name="Future Co",
        contact_name="Future Contact",
        email="future@example.com",
    )

    assert created is True
    assert lead.source == Lead.Source.OTHER
    assert lead.source_metadata["provider"] == "some_future_provider"
