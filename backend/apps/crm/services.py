"""CP9/CP10: reusable service functions for CRM domain operations.

Following the CP5/CP8 pattern: narrow, single-purpose, independently
testable functions for operations with real behavior beyond a single ORM
call. Plain single-field updates that need no extra rule (e.g. renaming a
customer) are NOT wrapped here — see CP7/CP8's own docs for why.

CP10 adds ``managed_user_ids()``/``scope_queryset_for_user()`` — the
"Employees see only their own records; Managers see their team's records;
Super Admins see everything" rule the CP10 API layer needs. This is
business logic (it decides WHICH rows a request is allowed to see), so per
CP10's own instructions ("views must call service-layer methods where
business logic exists") it lives here, not inline in ``views.py`` — and
it's the SAME function both ``views.py``'s ``get_queryset()`` and
``models.py``'s ``manager_has_access()`` hooks call, so list results and
individual object-permission checks can never disagree about who a Manager
can see.
"""
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import PermissionDenied

from apps.accounts.permissions import is_super_admin, user_has_role_at_least
from apps.accounts.models import User
from apps.core.utils import stamp_audit_fields
from apps.organization.models import Membership, Team

from .models import Address, ContactPerson, Customer, Lead
from .opportunities import Opportunity, OpportunityActivity, OpportunityNote


def create_customer(organization, name, *, owner=None, slug=None, **extra_fields):
    """Create a ``Customer`` under ``organization``.

    ``slug`` is derived from ``name`` via ``slugify()`` when not supplied —
    a caller building a "new customer" form does not need to separately
    compute one, but an API consumer that wants a specific slug still can.
    """
    if not slug:
        slug = slugify(name)
    return Customer.objects.create(organization=organization, name=name, slug=slug, owner=owner, **extra_fields)


def create_lead(company_name, contact_name, *, owner=None, **extra_fields):
    """Create a ``Lead``. A thin wrapper today — kept as a service function
    (rather than inlined ``Lead.objects.create()`` at every call site) so
    future lead-intake rules (deduplication, auto-assignment) have exactly
    one place to be added without touching every caller.
    """
    return Lead.objects.create(company_name=company_name, contact_name=contact_name, owner=owner, **extra_fields)


@transaction.atomic
def convert_lead(lead, organization, *, owner=None, slug=None, **extra_customer_fields):
    """Convert ``lead`` into a real ``Customer`` under ``organization``.

    Raises ``ValueError`` if the lead has already been converted — a lead
    can only become a customer once; calling this a second time is a
    caller error, not something to silently no-op or overwrite. The new
    ``Customer``'s ``name``/``email``/``phone`` default to the lead's own
    ``company_name``/``email``/``phone`` unless explicitly overridden via
    ``extra_customer_fields`` — a caller correcting/enriching data at
    conversion time (e.g. a properly capitalized company name) can still do
    so in the same call.

    On success: creates the ``Customer``, links ``lead.converted_customer``
    to it, and advances ``lead.status`` to ``Lead.Status.CONVERTED`` — all
    three happen together so a lead is never left half-converted (linked to
    a customer but still showing an earlier pipeline status, or vice versa).

    "Together" is now enforced by ``@transaction.atomic`` rather than only
    intended by the ordering of the statements below (Phase 4
    transaction-safety audit). Conversion is genuinely two writes against
    two tables: a brand-new ``Customer`` row, then the ``Lead`` update that
    points at it. If the second write fails for any reason — a database
    error, a constraint, a signal receiver raising — the un-transacted
    version left the ``Customer`` committed and permanently orphaned: a
    customer nobody asked for, owned by the lead's owner, appearing in
    their customer list, while the lead itself still showed as
    unconverted and could be converted AGAIN into a second duplicate
    customer. The already-converted guard above cannot catch that, because
    the flag it reads is exactly the write that didn't happen.
    """
    if lead.is_converted:
        raise ValueError("This lead has already been converted.")

    name = extra_customer_fields.pop("name", lead.company_name)
    email = extra_customer_fields.pop("email", lead.email)
    phone = extra_customer_fields.pop("phone", lead.phone)

    customer = create_customer(
        organization,
        name,
        owner=owner or lead.owner,
        slug=slug,
        email=email,
        phone=phone,
        **extra_customer_fields,
    )

    lead.converted_customer = customer
    lead.status = Lead.Status.CONVERTED
    lead.save(update_fields=["converted_customer", "status", "updated_at"])
    return customer


def _normalize_email(value):
    """Lowercased, whitespace-trimmed email, for duplicate comparison
    only — the stored field is left exactly as entered. Email addresses
    are case-insensitive at the mailbox-domain level for every real
    provider that matters here, so ``Jane@Acme.example`` and
    ``jane@acme.example`` are the same contact, not two.
    """
    return (value or "").strip().lower()


def _normalize_phone(value):
    """Digits-only phone number, for duplicate comparison only — the
    stored field is left exactly as entered.

    Without this, ``"555-0100"``, ``"(555) 0100"``, and ``"555 0100"``
    compared as three different phone numbers under a plain equality
    filter, so the same contact submitted twice with differently
    formatted phone numbers (a near-certainty across a CSV import, a
    manual entry, and a future external lead source) was never flagged
    as a duplicate at all — the exact gap CP9's original "exact match
    only" note called out as acceptable for NAME but not for the actual
    identifying fields.
    """
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _duplicate_candidates(email, phone, *, exclude_pk=None):
    """Shared matching core for ``find_duplicate_leads()`` (an existing,
    saved lead) and ``find_existing_lead_by_contact()`` (contact details
    that don't belong to a saved lead yet, e.g. one row of a CSV import
    being validated before it is created). Active, unconverted leads only,
    matched on normalized ``email``/``phone`` — see
    ``_normalize_email()``/``_normalize_phone()``.
    """
    normalized_email = _normalize_email(email)
    normalized_phone = _normalize_phone(phone)
    if not normalized_email and not normalized_phone:
        return Lead.active_objects.none()

    # A loose SQL prefilter (case-insensitive email, or ANY non-empty
    # phone) narrows the candidate set portably across every DB backend
    # this project runs against; the real, normalized comparison happens
    # in Python below since phone formatting can't be stripped in a
    # backend-portable SQL expression.
    criteria = Q()
    if normalized_email:
        criteria |= Q(email__iexact=normalized_email)
    if normalized_phone:
        criteria |= ~Q(phone="")

    candidates = Lead.active_objects.filter(criteria).exclude(status=Lead.Status.CONVERTED)
    if exclude_pk is not None:
        candidates = candidates.exclude(pk=exclude_pk)

    matched_ids = [
        candidate.pk
        for candidate in candidates
        if (normalized_email and _normalize_email(candidate.email) == normalized_email)
        or (normalized_phone and _normalize_phone(candidate.phone) == normalized_phone)
    ]
    return Lead.active_objects.filter(pk__in=matched_ids)


def find_duplicate_leads(lead):
    """Other active, unconverted ``Lead``s that plausibly refer to the same
    real-world contact as ``lead``: a matching non-empty ``email`` or a
    matching non-empty ``phone``, compared case-/format-insensitively (see
    ``_normalize_email()``/``_normalize_phone()``) so ``Jane@Acme.example``
    and ``jane@acme.example``, or ``555-0100`` and ``(555) 0100``, are
    correctly recognised as the same contact. Deliberately conservative
    beyond that (no fuzzy name matching) — a false-positive merge is
    destructive, a missed duplicate is just an extra manual check.
    """
    if lead.pk is None:
        return Lead.active_objects.none()
    return _duplicate_candidates(lead.email, lead.phone, exclude_pk=lead.pk)


def find_existing_lead_by_contact(email, phone):
    """The first active, unconverted ``Lead`` matching ``email``/``phone``
    (normalized — see ``_duplicate_candidates()``), for contact details
    that don't belong to a saved ``Lead`` yet. ``None`` when there is no
    match or neither value is supplied.

    Used by ``imports.py``'s ``import_leads()`` so a bulk import checks
    each row against leads ALREADY in the system before creating one —
    the same normalized comparison ``find_duplicate_leads()`` applies to
    two already-saved leads, just run one step earlier.
    """
    return _duplicate_candidates(email, phone).first()


@transaction.atomic
def merge_leads(primary, duplicate, *, merged_by=None):
    """Merge ``duplicate`` into ``primary``: every record elsewhere in the
    system that points at ``duplicate`` via a generic (content_type +
    object_id) relation — activities, tasks, reminders, communications,
    audit log entries, workflow executions, anything built on
    ``apps.activities.models.RelatedToEntityModel`` — is repointed at
    ``primary`` instead, so nothing referencing the duplicate becomes an
    orphaned/dangling reference. Empty fields on ``primary`` are backfilled
    from ``duplicate`` (never overwritten if ``primary`` already has a
    value); notes are concatenated, not dropped. ``duplicate`` is then
    SOFT-deleted, never hard-deleted — the merge itself must stay
    auditable/reversible, matching CP7's "no permanent delete unless
    explicitly requested" rule; its own record (and the trail of what it
    used to contain) is preserved, just marked deleted and no longer the
    lead of record.

    Raises ``ValueError`` for merging a lead with itself or merging an
    already-converted lead (a converted lead is a customer now — its
    history belongs to that customer, not to another lead).
    """
    if primary.pk == duplicate.pk:
        raise ValueError("Cannot merge a lead with itself.")
    if primary.is_converted or duplicate.is_converted:
        raise ValueError("Cannot merge a converted lead — convert or merge before conversion, not after.")

    from django.apps import apps as django_apps
    from django.contrib.contenttypes.models import ContentType

    from apps.activities.models import RelatedToEntityModel

    lead_content_type = ContentType.objects.get_for_model(Lead)

    for model in django_apps.get_models():
        if not issubclass(model, RelatedToEntityModel) or model._meta.abstract:
            continue
        model.objects.filter(content_type=lead_content_type, object_id=duplicate.pk).update(object_id=primary.pk)

    for field in ("email", "phone"):
        if not getattr(primary, field) and getattr(duplicate, field):
            setattr(primary, field, getattr(duplicate, field))
    if duplicate.notes:
        merged_note = f"--- Merged from duplicate lead #{duplicate.pk} ({duplicate.company_name}) ---\n{duplicate.notes}"
        primary.notes = f"{primary.notes}\n\n{merged_note}".strip() if primary.notes else merged_note
    if primary.owner_id is None and duplicate.owner_id is not None:
        primary.owner = duplicate.owner
    primary.updated_by = merged_by
    primary.save()

    duplicate.notes = (f"Merged into lead #{primary.pk}.\n\n{duplicate.notes}").strip()
    duplicate.soft_delete(updated_by=merged_by)

    return primary


def assign_owner(instance, user):
    """Assign (or clear, with ``user=None``) the ``owner`` of a ``Customer``
    or ``Lead`` — anything with an ``owner`` FK. A thin wrapper (mirroring
    CP8's ``set_team_manager()``) so a future ownership rule (e.g. "the new
    owner must be Manager-or-above") has one place to live.
    """
    instance.owner = user
    instance.save(update_fields=["owner", "updated_at"])
    return instance


class OwnerAssignmentNotAllowed(PermissionDenied):
    """Raised by ``resolve_owner_for_create()`` when the requester tried to
    attribute a new record to a user they're not allowed to assign.
    Subclasses DRF's own ``PermissionDenied`` so every caller gets an
    automatic 403 with this message from DRF's exception handler,
    without needing its own try/except.
    """


def resolve_owner_for_create(user, requested_owner):
    """Final internet-facing security audit, Part 15: the owner to assign
    a newly-created, owner-having record to, given an optional
    client-requested owner — the rule every ``perform_create()`` across
    the project (Lead, Customer, Opportunity, Quote, Invoice, Task,
    Event, SavedReport, Dashboard, Workflow, Integration, BackgroundJob)
    now goes through instead of accepting ``requested_owner`` unchecked.

    - No ``requested_owner`` supplied (``None``): defaults to ``user``
      themselves — unchanged from every checkpoint's original behavior.
    - ``requested_owner == user``: always allowed (creating your own
      record).
    - Super Admin: may assign to anyone.
    - Manager: may assign to anyone in their own ``managed_user_ids()``
      (themselves + their teams' members) — the same boundary already
      enforced for reads via ``scope_queryset_for_user()``.
    - Employee (or anyone else) requesting a DIFFERENT owner: rejected.
      Previously accepted unconditionally — any authenticated user could
      attribute a brand-new record to an arbitrary other user, a
      data-integrity gap even though it never granted access to an
      EXISTING record (see the BOLA fix in the prior audit pass for
      that, separate, class of issue).
    """
    if requested_owner is None:
        return user
    if requested_owner.pk == user.pk:
        return requested_owner
    if is_super_admin(user):
        return requested_owner
    if user_has_role_at_least(user, User.Role.MANAGER) and requested_owner.pk in managed_user_ids(user):
        return requested_owner
    raise OwnerAssignmentNotAllowed("You are not allowed to assign this record to that owner.")


class LeadAssignmentNotAllowed(PermissionDenied):
    """Raised by ``assign_leads()`` when the caller may not perform the
    requested assignment. Subclasses DRF's ``PermissionDenied`` (same
    reasoning as ``OwnerAssignmentNotAllowed`` above) so the API layer
    returns a 403 without its own try/except.
    """


#: Accepted ``target_type`` values for ``assign_leads()``, mapped to the
#: role the target user must actually hold. "Assign to a manager" must
#: never quietly assign to an employee (or vice versa) just because the
#: caller passed the wrong id.
ASSIGNMENT_TARGET_ROLES = {
    "manager": User.Role.MANAGER,
    "employee": User.Role.EMPLOYEE,
}


def can_assign_leads(user):
    """Only Manager-or-above may assign leads at all. An Employee can
    never assign a lead — not to themselves, not to anyone (the spec's
    "Employees cannot assign leads" rule, enforced in the data layer, not
    by hiding a button).
    """
    return user_has_role_at_least(user, User.Role.MANAGER)


def validate_assignment_target(actor, target_user, target_type):
    """Resolve and authorize the user ``actor`` wants to assign leads TO.

    - ``target_type`` must be ``"manager"`` or ``"employee"``, and
      ``target_user.role`` must actually match it.
    - The target must be active — assigning work to a deactivated account
      would silently orphan it.
    - Super Admin: any valid target.
    - Manager: only a target inside their own ``managed_user_ids()``, and
      never another Manager other than themselves (a Manager may take a
      lead themselves, but may not hand work to a peer manager or to the
      Super Admin).
    """
    if target_type not in ASSIGNMENT_TARGET_ROLES:
        raise LeadAssignmentNotAllowed("target_type must be 'manager' or 'employee'.")
    if target_user is None:
        raise LeadAssignmentNotAllowed("The assignment target does not exist.")
    if target_user.role != ASSIGNMENT_TARGET_ROLES[target_type]:
        raise LeadAssignmentNotAllowed(
            f"Target user is not a {target_type}; their role is {target_user.role}."
        )
    if not target_user.is_active:
        raise LeadAssignmentNotAllowed("Cannot assign leads to a deactivated account.")

    if is_super_admin(actor):
        return target_user
    if not can_assign_leads(actor):
        raise LeadAssignmentNotAllowed("You are not allowed to assign leads.")
    if target_user.pk == actor.pk:
        return target_user
    if target_user.pk in managed_user_ids(actor):
        return target_user
    raise LeadAssignmentNotAllowed("You may only assign leads to employees within your own scope.")


@transaction.atomic
def assign_leads(actor, lead_ids, target_type, target_user):
    """Bulk (re)assign leads to ``target_user``. Returns the updated
    ``Lead`` objects, in the order they were found.

    Two independent authorization checks, both required:

    1. ``validate_assignment_target()`` — may ``actor`` assign work TO
       this user at all (role/scope/active checks above).
    2. Every lead must ALREADY be visible to ``actor`` under
       ``scope_queryset_for_user()`` — the same boundary every read uses.
       A lead outside that scope is reported as not found rather than
       silently skipped, so a Manager can never reassign another team's
       lead by guessing its id.

    Reassignment of an already-assigned lead is explicitly supported (the
    spec's "reassign previously assigned leads") — there is no "already
    owned" guard, only the two authorization checks above.
    """
    target_user = validate_assignment_target(actor, target_user, target_type)

    ids = list(dict.fromkeys(lead_ids or []))
    if not ids:
        raise LeadAssignmentNotAllowed("lead_ids must contain at least one lead id.")

    visible = scope_queryset_for_user(Lead.active_objects.all(), actor)
    leads = list(visible.filter(pk__in=ids))
    found_ids = {lead.pk for lead in leads}
    missing = [lead_id for lead_id in ids if lead_id not in found_ids]
    if missing:
        raise Lead.DoesNotExist(f"Leads not found or not accessible: {missing}")

    for lead in leads:
        lead.owner = target_user
        lead.updated_by = actor
        lead.save(update_fields=["owner", "updated_by", "updated_at"])
    return leads


def add_contact(customer, first_name, last_name, *, is_primary=False, **extra_fields):
    """Add a ``ContactPerson`` to ``customer``.

    If ``is_primary=True``, any existing primary contact for this customer
    is demoted first — without this, creating a second primary contact
    would simply fail against the DB's partial unique constraint (see
    ``models.py``). This makes "promote a new primary contact" a single,
    safe call instead of a two-step "demote, then create" the caller would
    otherwise have to remember.
    """
    if is_primary:
        ContactPerson.objects.filter(customer=customer, is_primary=True).update(is_primary=False)
    return ContactPerson.objects.create(
        customer=customer, first_name=first_name, last_name=last_name, is_primary=is_primary, **extra_fields
    )


def add_address(customer, address_type, **fields):
    """Add an ``Address`` to ``customer``. A thin wrapper — kept as a
    service function for symmetry with ``add_contact()`` and so a future
    "only one billing address per customer" rule (unlike contacts, not
    requested by CP9) would have one place to be added.
    """
    return Address.objects.create(customer=customer, address_type=address_type, **fields)


class ExternalLeadIngestionError(ValueError):
    """Raised by ``ingest_external_lead()`` for malformed input — missing
    required contact fields, a missing ``external_source_id``, or a blank
    ``provider``. A caller error (bad payload from whatever future
    webhook/connector calls this), not a server fault, so it deliberately
    is NOT a DRF ``PermissionDenied``/``ValidationError`` subclass — this
    function has no HTTP framing of its own yet (no view calls it today;
    see this function's own docstring), so it raises a plain, catchable
    Python exception a future view can translate into a 400 however that
    view's own error-response shape works.
    """


#: Maps a known external ``provider`` identifier to the closest existing
#: ``Lead.Source`` choice, purely for the ``source`` column's own filtering/
#: reporting UI (the "Source" dropdown Leads are already filtered by
#: elsewhere in this project) to have a sensible value. This is a
#: convenience only — the RAW, unmapped ``provider`` string is always also
#: preserved verbatim in ``source_metadata["provider"]``, so no information
#: is lost for a provider not listed here (or a future provider added
#: later); it simply falls back to ``Lead.Source.OTHER``.
EXTERNAL_LEAD_PROVIDER_SOURCE_MAP = {
    "website": Lead.Source.WEBSITE,
    "website_webhook": Lead.Source.WEBSITE,
    "meta": Lead.Source.ADVERTISEMENT,
    "facebook": Lead.Source.ADVERTISEMENT,
    "facebook_lead_ads": Lead.Source.ADVERTISEMENT,
    "google_ads": Lead.Source.ADVERTISEMENT,
    "whatsapp": Lead.Source.OTHER,
}


def _lock_existing_lead_by_external_id(external_source_id):
    """Row-locking existence check for ``ingest_external_lead()``, pulled
    out as its own function purely so a test can monkeypatch this ONE
    call to deterministically simulate "another request already inserted
    the row between this SELECT and our INSERT" — the exact race
    ``ingest_external_lead()``'s ``IntegrityError`` handling exists for —
    without needing a genuinely separate DB connection/thread. See
    ``apps/crm/tests/test_ingest_external_lead.py``'s concurrency test for
    why: a real multi-connection race was tried first and hit an
    unrelated, pre-existing environment limitation in this project's test
    database teardown.
    """
    return Lead.objects.select_for_update().filter(external_source_id=external_source_id).first()


def ingest_external_lead(
    *,
    provider,
    external_source_id,
    company_name,
    contact_name,
    email="",
    phone="",
    source_metadata=None,
    received_at=None,
    notes="",
):
    """Generic, provider-agnostic entry point for a FUTURE external lead
    source (a Meta/Google Ads lead-form webhook, a WhatsApp Business
    inbound-message-to-lead flow, a website contact-form webhook, ...) to
    hand a raw lead payload to this system and get back exactly one
    ``Lead`` row — never two, no matter how many times the same external
    event is redelivered.

    This function builds ONLY the service-layer contract. No view/URL
    calls it yet (see ``urls.py`` — there is deliberately no webhook
    endpoint in this pass); wiring an actual Meta/Google Ads/WhatsApp/
    website integration is explicitly OUT of scope here. A future webhook
    view's entire job is: authenticate the inbound request, map that
    provider's payload shape onto this function's keyword arguments, and
    call it — no duplicate-detection or idempotency logic of its own.

    Returns ``(lead, created)`` — ``created`` is ``True`` only when a new
    ``Lead`` row was actually written, mirroring Django's own
    ``get_or_create()`` return shape so a caller can log/branch on it
    without inventing its own convention.

    Pipeline, in order:

    1. **Validate.** ``provider`` and ``external_source_id`` must both be
       non-empty (see "Idempotency contract" below); ``company_name`` and
       ``contact_name`` must both be non-empty — the same two fields
       ``Lead.company_name``/``Lead.contact_name`` require at the model
       level (``blank=False``), enforced HERE because this function calls
       ``Lead.objects.create()`` directly rather than going through a
       serializer's own validation. Anything missing raises
       ``ExternalLeadIngestionError`` — never a silent garbage row, never
       an unhandled ``IntegrityError``/``django.core.exceptions.
       ValidationError`` bubbling out of the ORM.
    2. **Idempotency short-circuit.** If a ``Lead`` with this exact
       ``external_source_id`` already exists, return it unchanged —
       ``(existing_lead, False)`` — without touching duplicate detection
       at all. This is deliberately checked BEFORE the email/phone
       duplicate scan: the same external event redelivered (a webhook
       retry, a re-run sync) is not a "possible duplicate contact" for a
       human to review, it is THE SAME LEAD, and must resolve identically
       every time.
    3. **Duplicate check.** Only for a genuinely new external id: reuses
       ``find_existing_lead_by_contact()`` (the same normalized email/
       phone matching ``imports.py``'s CSV/Google Sheets bulk import
       already applies) so an external lead that is really the same
       CONTACT as one already in the system — entered by hand, imported,
       or ingested from a different provider — still lands on that
       existing ``Lead`` instead of creating a second row for the same
       real person. This is a courtesy match, not a hard idempotency
       guarantee the way ``external_source_id`` is (see "Known
       limitation" below) — it is best-effort, exactly like every other
       caller of ``find_existing_lead_by_contact()``.
    4. **Create-or-return.** Create the ``Lead`` with ``external_source_id``
       set, ``source`` mapped from ``provider`` (see
       ``EXTERNAL_LEAD_PROVIDER_SOURCE_MAP``), and the raw ``provider``
       string plus caller-supplied ``source_metadata`` merged into
       ``source_metadata`` on the row. ``owner`` is deliberately left
       unset — assignment is a separate, later step (routing/auto-assign
       rules), not this function's job.
    5. **Audit event.** A brand-new ``Lead`` is already covered for free —
       ``apps.system.signals``'s existing ``post_save`` receiver logs a
       ``CREATE`` ``AuditLog`` entry for every ``Lead`` saved, ingestion
       included. For the idempotent-duplicate-request path (step 2, no
       save happens, so no signal fires) this function logs its OWN
       explicit ``AuditLog`` entry — action ``OTHER`` — so "the same
       external event arrived again" is still an observable, auditable
       fact, not a silent no-op.

    Idempotency under a race. Two concurrent requests for the same
    ``provider``+``external_source_id`` (a webhook firing twice at once)
    must both resolve to the SAME single ``Lead``, never a raised
    ``IntegrityError`` and never two rows. The whole function runs inside
    ``transaction.atomic()``; the existence check uses
    ``select_for_update()`` so a second concurrent caller blocks behind
    the first's row-level lock (on a backend that honors it — see
    ``SAVEPOINT`` note below) rather than racing past it, and the
    ``Lead.objects.create()`` call is additionally wrapped in its own
    nested atomic block (a SAVEPOINT) so that IF the DB-level
    ``UniqueConstraint`` on ``external_source_id`` (see ``models.py``)
    still fires — the last-resort guarantee under a backend/isolation
    level where the row lock alone isn't enough — the ``IntegrityError``
    is caught, the savepoint is rolled back cleanly (leaving the OUTER
    transaction healthy), and the row that won the race is re-fetched and
    returned instead of letting a raw 500 escape.

    Known limitation (Q3's own framing): the ``UniqueConstraint`` this
    function relies on is declared on ``external_source_id`` ALONE, not on
    ``(source, external_source_id)`` or ``(provider, external_source_id)``
    — there is currently a single GLOBAL namespace for external ids, not
    one namespaced per provider. Two different providers that happen to
    reuse the exact same raw id string (e.g. both assign ids ``"1"``,
    ``"2"``, ``"3"``, ...) would collide and the second provider's lead
    would be silently treated as a duplicate of the first's. This is
    flagged here deliberately rather than fixed: changing the DB
    constraint is a migration/schema change outside "build the service
    layer", and no real provider integration exists yet to confirm this
    is an actual problem in practice (Meta/Google/WhatsApp ids are
    already provider-specific-format strings vanishingly unlikely to
    collide with each other). A future integration pass that DOES observe
    a real collision, or that onboards a provider with short/numeric ids,
    should namespace this — e.g. prefixing ``external_source_id`` with
    ``f"{provider}:"`` at the call site costs nothing today and sidesteps
    the limitation without touching the schema at all; that prefixing is
    deliberately NOT done automatically by this function, since it would
    change the stored value for every future caller unconditionally
    rather than leaving it as an opt-in choice.
    """
    provider = (provider or "").strip()
    external_source_id = (external_source_id or "").strip()
    company_name = (company_name or "").strip()
    contact_name = (contact_name or "").strip()

    if not provider:
        raise ExternalLeadIngestionError("provider is required.")
    if not external_source_id:
        raise ExternalLeadIngestionError(
            "external_source_id is required — ingest_external_lead() exists specifically to "
            "provide idempotent external ingestion; a lead with no stable external id should "
            "be created via create_lead() instead, which has no idempotency contract to break."
        )
    if not company_name:
        raise ExternalLeadIngestionError("company_name is required.")
    if not contact_name:
        raise ExternalLeadIngestionError("contact_name is required.")
    if not email and not phone:
        raise ExternalLeadIngestionError("At least one of email or phone is required.")

    merged_metadata = dict(source_metadata or {})
    merged_metadata.setdefault("provider", provider)
    mapped_source = EXTERNAL_LEAD_PROVIDER_SOURCE_MAP.get(provider.lower(), Lead.Source.OTHER)

    with transaction.atomic():
        existing = _lock_existing_lead_by_external_id(external_source_id)
        if existing is not None:
            _log_ingestion_duplicate(provider, external_source_id, existing)
            return existing, False

        duplicate = find_existing_lead_by_contact(email, phone)
        if duplicate is not None and not duplicate.external_source_id:
            # A contact match against a lead with NO external id of its
            # own (entered by hand, or imported) — attach this
            # provider's id to it rather than creating a second row for
            # the same real contact. A lead that already carries a
            # DIFFERENT provider's external_source_id is left alone and
            # falls through to creating a new row: it is already owned by
            # another external identity and re-stamping it here would
            # silently sever that other provider's own idempotency link.
            duplicate.external_source_id = external_source_id
            duplicate.source_metadata = {**duplicate.source_metadata, **merged_metadata}
            if received_at is not None:
                duplicate.received_at = received_at
            duplicate.save(update_fields=["external_source_id", "source_metadata", "received_at", "updated_at"])
            return duplicate, False

        try:
            with transaction.atomic():
                lead = Lead.objects.create(
                    company_name=company_name,
                    contact_name=contact_name,
                    email=email,
                    phone=phone,
                    source=mapped_source,
                    external_source_id=external_source_id,
                    source_metadata=merged_metadata,
                    received_at=received_at,
                    notes=notes,
                )
        except IntegrityError:
            # Lost a race against another concurrent ingestion of the
            # SAME external_source_id between our SELECT above and this
            # INSERT (possible under isolation levels/backends where
            # select_for_update() alone doesn't fully serialize two
            # inserts) — the DB-level UniqueConstraint is the final
            # backstop. Re-fetch and return the row that won instead of
            # letting the IntegrityError escape as an unhandled 500.
            lead = Lead.objects.get(external_source_id=external_source_id)
            return lead, False

    return lead, True


def _log_ingestion_duplicate(provider, external_source_id, existing_lead):
    """Records an explicit audit trail entry for a repeated external
    ingestion request that resolved to an already-existing ``Lead`` (no
    model save happens on this path, so ``apps.system.signals``'s
    automatic post-save audit logging never fires for it — see
    ``ingest_external_lead()``'s own docstring, step 5).

    Broad ``try/except`` for the same reason ``apps.system.signals``'s own
    receiver has one: a logging failure must never break ingestion
    idempotency itself — returning the existing lead is the important,
    correctness-bearing behavior; failing to also log that it happened
    again is a much smaller problem.
    """
    try:
        from apps.system.services import log_audit_event
        from apps.system.models import AuditLog

        log_audit_event(
            None,
            AuditLog.Action.OTHER,
            related_object=existing_lead,
            description=(
                f"Duplicate external lead ingestion ignored (provider={provider!r}, "
                f"external_source_id={external_source_id!r}) — resolved to existing lead "
                f"id={existing_lead.pk}."
            ),
        )
    except Exception:  # noqa: BLE001 - deliberate, see docstring
        import logging

        logging.getLogger(__name__).exception(
            "Failed to log duplicate-ingestion audit event for lead id=%s", existing_lead.pk
        )


def managed_user_ids(manager):
    """All user IDs ``manager`` is considered to "manage": themselves, plus
    every member of every ``apps.organization`` ``Team`` they manage.

    This is the single place "which users does this Manager see" is
    computed — reused identically by ``scope_queryset_for_user()`` (list
    results) and by ``Customer``/``Lead.manager_has_access()`` (individual
    object-permission checks), so the two can never disagree about who a
    given Manager can reach.
    """
    team_ids = Team.objects.filter(manager=manager).values_list("id", flat=True)
    member_ids = set(Membership.objects.filter(team_id__in=team_ids).values_list("user_id", flat=True))
    member_ids.add(manager.id)
    return member_ids


def scope_queryset_for_user(queryset, user, owner_field="owner"):
    """Filter ``queryset`` to what ``user`` is allowed to see:

    - Super Admin: everything, unfiltered.
    - Manager (or above): records owned by anyone in ``managed_user_ids()``
      (themselves + their teams' members).
    - Employee: only records they own themselves.
    - Anonymous/unauthenticated: nothing.

    ``owner_field`` is the ORM path from ``queryset``'s model to the
    ``User`` that owns each row — ``"owner"`` for ``Customer``/``Lead``
    (a real FK), or ``"customer__owner"`` for ``ContactPerson``/``Address``
    (which have no ``owner`` column of their own, only the ``owner``
    *property* defined in ``models.py`` that Python-level code like
    ``resolve_owner()`` can use but the ORM cannot filter on directly).

    This is the list-level counterpart to ``Customer``/``Lead
    .manager_has_access()`` — both ultimately consult
    ``managed_user_ids()``, so a Manager's list results and their
    individual object access never disagree about who they can reach.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return queryset.none()
    if is_super_admin(user):
        return queryset
    if user_has_role_at_least(user, User.Role.MANAGER):
        return queryset.filter(**{f"{owner_field}_id__in": managed_user_ids(user)})
    return queryset.filter(**{owner_field: user})


# --------------------------------------------------------------------------
# CP11: Opportunity pipeline
# --------------------------------------------------------------------------


def create_opportunity(customer, title, *, owner=None, **extra_fields):
    """Create an ``Opportunity`` against ``customer``.

    A thin wrapper today (no behavior beyond ``.create()``) — kept as a
    service function anyway for the same reason ``create_lead()`` is: one
    seam for a future intake rule (e.g. auto-assigning a default
    ``probability`` per ``stage``) rather than none at all.
    """
    return Opportunity.objects.create(customer=customer, title=title, owner=owner, **extra_fields)


def advance_stage(opportunity, stage):
    """Move ``opportunity`` to a new, still-open pipeline ``stage``.

    Raises ``ValueError`` if the opportunity is already closed (``WON`` or
    ``LOST``) — per CP11's rule, "cannot move past WON/LOST unless
    reopened"; ``reopen()`` is the only way back into the open pipeline.
    Also raises ``ValueError`` if ``stage`` is ``WON``/``LOST`` — closing an
    opportunity is a distinct, richer operation (see ``mark_won()``/
    ``mark_lost()``, which set ``is_closed``/``is_won``/
    ``actual_close_date`` together) that a bare stage assignment must not
    be able to trigger as a side effect.
    """
    if opportunity.is_closed:
        raise ValueError("Cannot change the stage of a closed opportunity — call reopen() first.")
    if stage in (Opportunity.Stage.WON, Opportunity.Stage.LOST):
        raise ValueError("Use mark_won()/mark_lost() to close an opportunity, not advance_stage().")

    opportunity.stage = stage
    opportunity.save(update_fields=["stage", "updated_at"])
    return opportunity


def mark_won(opportunity, *, actual_close_date=None):
    """Close ``opportunity`` as WON.

    Sets ``stage=WON``, ``is_closed=True``, ``is_won=True``, and
    ``actual_close_date`` (defaulting to today) all together — CP11's rule
    that WON "automatically sets" these three fields, so a caller can never
    end up with one set without the others. Raises ``ValueError`` if the
    opportunity is already closed — winning an already-closed opportunity
    a second time is a caller error, not a no-op.
    """
    if opportunity.is_closed:
        raise ValueError("This opportunity is already closed.")

    opportunity.stage = Opportunity.Stage.WON
    opportunity.is_closed = True
    opportunity.is_won = True
    opportunity.actual_close_date = actual_close_date or timezone.now().date()
    opportunity.save(update_fields=["stage", "is_closed", "is_won", "actual_close_date", "updated_at"])
    return opportunity


def mark_lost(opportunity, *, actual_close_date=None):
    """Close ``opportunity`` as LOST.

    Sets ``stage=LOST``, ``is_closed=True``, ``is_won=False``, and
    ``actual_close_date`` — the LOST counterpart to ``mark_won()``, same
    "already closed" guard and same reasoning.
    """
    if opportunity.is_closed:
        raise ValueError("This opportunity is already closed.")

    opportunity.stage = Opportunity.Stage.LOST
    opportunity.is_closed = True
    opportunity.is_won = False
    opportunity.actual_close_date = actual_close_date or timezone.now().date()
    opportunity.save(update_fields=["stage", "is_closed", "is_won", "actual_close_date", "updated_at"])
    return opportunity


def reopen(opportunity, *, stage=Opportunity.Stage.NEW):
    """Reverse ``mark_won()``/``mark_lost()`` — clears ``is_closed``,
    ``is_won``, and ``actual_close_date`` (CP11's rule: "reopen() clears
    closing fields") and returns the opportunity to ``stage`` (``NEW`` by
    default — back to the start of the pipeline, since reopening usually
    means the deal genuinely needs re-qualifying, not that it silently
    resumes from wherever it happened to be closed). Raises ``ValueError``
    if the opportunity isn't currently closed — nothing to reopen.
    """
    if not opportunity.is_closed:
        raise ValueError("This opportunity is not closed.")
    if stage in (Opportunity.Stage.WON, Opportunity.Stage.LOST):
        raise ValueError("reopen() must return the opportunity to an OPEN stage, not WON/LOST.")

    opportunity.stage = stage
    opportunity.is_closed = False
    opportunity.is_won = False
    opportunity.actual_close_date = None
    opportunity.save(update_fields=["stage", "is_closed", "is_won", "actual_close_date", "updated_at"])
    return opportunity


def add_note(opportunity, content, *, created_by=None):
    """Add an ``OpportunityNote`` to ``opportunity``, stamping
    ``created_by``/``updated_by`` via CP7's ``stamp_audit_fields()`` when a
    user is supplied — mirrors CP9's ``add_contact()``/``add_address()``
    shape (a thin wrapper today, kept as a service function for the same
    single-seam reasoning).
    """
    note = OpportunityNote.objects.create(opportunity=opportunity, content=content)
    if created_by is not None:
        stamp_audit_fields(note, created_by, creating=True)
        note.save()
    return note


def add_activity(opportunity, activity_type, subject, *, notes="", occurred_at=None, created_by=None):
    """Add an ``OpportunityActivity`` to ``opportunity``. Same shape and
    reasoning as ``add_note()``.
    """
    activity = OpportunityActivity.objects.create(
        opportunity=opportunity,
        activity_type=activity_type,
        subject=subject,
        notes=notes,
        occurred_at=occurred_at or timezone.now(),
    )
    if created_by is not None:
        stamp_audit_fields(activity, created_by, creating=True)
        activity.save()
    return activity


__all__ = [
    "create_customer",
    "create_lead",
    "convert_lead",
    "assign_owner",
    "resolve_owner_for_create",
    "OwnerAssignmentNotAllowed",
    "LeadAssignmentNotAllowed",
    "ASSIGNMENT_TARGET_ROLES",
    "can_assign_leads",
    "validate_assignment_target",
    "assign_leads",
    "add_contact",
    "add_address",
    "ExternalLeadIngestionError",
    "EXTERNAL_LEAD_PROVIDER_SOURCE_MAP",
    "ingest_external_lead",
    "managed_user_ids",
    "scope_queryset_for_user",
    "create_opportunity",
    "advance_stage",
    "mark_won",
    "mark_lost",
    "reopen",
    "add_note",
    "add_activity",
]
