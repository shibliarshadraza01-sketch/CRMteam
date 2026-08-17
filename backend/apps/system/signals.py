"""CP19: audit-logging signal receivers.

Connected from `apps.py`'s `AppConfig.ready()` — the standard, non-invasive
Django mechanism for observing an EXISTING model's lifecycle without
editing that model's own file at all. This module is the ENTIRE
implementation of CP19's "integrate audit logging with existing apps
where appropriate" requirement: it touches ZERO lines in `apps.crm`/
`apps.sales`, so "without changing existing business behavior" is true by
CONSTRUCTION, not by careful editing — the same restraint CP15/CP16/CP17
each applied to not widening an already-shipped checkpoint's own files,
turned around: this IS the checkpoint whose job is exactly this kind of
integration (see BACKEND_LEARNING_GUIDE.md CP19).

Audited models are a deliberately CURATED set — the core CRM/sales
records a compliance/audit-trail requirement would actually care about
(`Customer`/`Lead`/`Opportunity`/`Quote`/`Invoice`, the same five models
CP14's `RELATABLE_ENTITY_TYPES` already recognizes as "the" CRM
entities) — not blanket-applied to every model in the project.

Every receiver is wrapped in a broad `try/except` that NEVER lets a
logging failure propagate: audit logging observing a save must never be
able to break the save itself. This is the one place in the signal path
where "never raise" is not just a design preference but a hard
requirement — a `Customer.save()` that started failing because
`apps.system` couldn't write a log row would be a MUCH worse regression
than a missed audit entry.
"""
from django.db.models.signals import post_save

from .models import AuditLog

#: dispatch_uid values so re-running register_audit_signals() (e.g. if
#: ever called twice, such as under a test runner that re-imports apps)
#: never double-connects the same receiver to the same model.
_DISPATCH_UID_PREFIX = "cp19_audit_log"


def _record_save(sender, instance, created, raw=False, **kwargs):
    """Shared receiver body for every audited model's `post_save`.

    `raw=True` (set by `loaddata`/fixture loading) is skipped — a fixture
    load is not a real user/system action worth auditing, and fixture
    rows often reference other rows not yet loaded, which
    `related_object`-style lookups could choke on.
    """
    if raw:
        return

    try:
        from .services import log_audit_event

        action = AuditLog.Action.CREATE if created else AuditLog.Action.UPDATE
        actor = instance.created_by if created else instance.updated_by
        log_audit_event(
            actor,
            action,
            related_object=instance,
            description=f"{sender.__name__} {'created' if created else 'updated'} (id={instance.pk})",
        )
    except Exception:  # noqa: BLE001 - deliberate: audit logging must never break the save it's observing
        import logging

        logging.getLogger(__name__).exception(
            "apps.system audit logging failed for %s(id=%s) — the underlying save was NOT affected.",
            sender.__name__,
            instance.pk,
        )


def register_audit_signals():
    """Connect `_record_save` to every audited model's `post_save`.

    Imports the target models INSIDE this function (not at module import
    time) — by the time `AppConfig.ready()` calls this, Django's app
    registry is fully populated for every app regardless of
    `INSTALLED_APPS` ordering, so this is always safe, the standard
    Django pattern for cross-app signal registration.
    """
    from apps.communications.models import Call, WhatsAppMessage
    from apps.crm.models import Customer, Lead
    from apps.crm.opportunities import Opportunity
    from apps.sales.models import Invoice, Quote

    # Final production operations pass: Call/WhatsAppMessage added —
    # both are real external-provider-facing communication records (a
    # placed phone call, a sent WhatsApp message), the same "compliance/
    # audit-trail-worthy" class of record as the original five, and
    # explicitly required by that pass's own spec ("Audit log required").
    for model in (Customer, Lead, Opportunity, Quote, Invoice, Call, WhatsAppMessage):
        post_save.connect(
            _record_save, sender=model, dispatch_uid=f"{_DISPATCH_UID_PREFIX}_{model._meta.label_lower}"
        )
