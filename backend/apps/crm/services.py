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
from django.utils import timezone
from django.utils.text import slugify

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


def assign_owner(instance, user):
    """Assign (or clear, with ``user=None``) the ``owner`` of a ``Customer``
    or ``Lead`` — anything with an ``owner`` FK. A thin wrapper (mirroring
    CP8's ``set_team_manager()``) so a future ownership rule (e.g. "the new
    owner must be Manager-or-above") has one place to live.
    """
    instance.owner = user
    instance.save(update_fields=["owner", "updated_at"])
    return instance


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
    "add_contact",
    "add_address",
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
