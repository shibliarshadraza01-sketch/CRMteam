"""CP7: reusable utility functions for soft delete, restore, audit stamping,
and common query helpers.

These exist so that future views/services (and, eventually, the deferred
audit middleware — see the module docstring in ``models.py``) call ONE
shared function rather than each reimplementing "how do I soft delete a
row" or "how do I stamp who touched this" slightly differently. Every
function here is deliberately a thin, testable wrapper around the model
methods already defined in ``models.py`` — no new business logic is
introduced, only a consistent call surface.
"""


def soft_delete(instance, *, updated_by=None):
    """Soft-delete a single ``SoftDeleteModel`` instance.

    Thin wrapper around ``instance.soft_delete()`` — exists so callers can
    depend on ``apps.core.utils`` as the one place this operation is
    performed from, without needing to know or care that it happens to be
    implemented as an instance method today (that's an implementation
    detail this function insulates callers from).
    """
    instance.soft_delete(updated_by=updated_by)
    return instance


def restore(instance, *, updated_by=None):
    """Restore a single soft-deleted ``SoftDeleteModel`` instance."""
    instance.restore(updated_by=updated_by)
    return instance


def bulk_soft_delete(queryset, *, updated_by=None):
    """Soft-delete every row in ``queryset``.

    Uses the queryset's own (overridden) ``.delete()`` — see
    ``SoftDeleteQuerySet.delete()`` — which is already a bulk soft delete,
    not a real SQL DELETE. ``updated_by``, if given, is stamped onto every
    affected row via a single extra ``UPDATE`` (kept separate from the
    ``.delete()`` call itself so this function works whether or not the
    caller wants audit stamping, without ``SoftDeleteQuerySet.delete()``
    needing to know about ``updated_by`` at all).
    """
    if updated_by is not None:
        queryset.update(updated_by=updated_by)
    return queryset.delete()


def bulk_restore(queryset, *, updated_by=None):
    """Restore every soft-deleted row in ``queryset``."""
    if updated_by is not None:
        queryset.update(updated_by=updated_by)
    return queryset.restore()


def stamp_audit_fields(instance, user, *, creating):
    """Set ``created_by``/``updated_by`` on ``instance`` for ``user``.

    Does NOT call ``save()`` — callers decide when to persist, so this can
    be used both right before a manual ``.save()`` call and, later, from
    inside a DRF serializer's ``create()``/``update()`` or a future
    middleware/signal without this function needing to know which.

    ``creating`` is required (not inferred from ``instance.pk`), because
    inferring "is this a create" from "does it have a pk yet" breaks for
    models with a non-auto-incrementing or client-supplied primary key —
    the caller already knows whether it's creating or updating, so this
    function trusts that instead of guessing.
    """
    if user is None:
        return instance

    if creating:
        instance.created_by = user
    instance.updated_by = user
    return instance


def active_queryset(model):
    """Return ``model``'s non-deleted rows, working for ANY model — one
    that mixes in ``SoftDeleteModel`` (uses ``active_objects``) or a plain
    model with no soft-delete support at all (falls back to
    ``objects.all()``).

    Exists so generic/reusable code (e.g. a future base ``ListAPIView``)
    can ask "give me the usable rows of this model" without needing to know
    in advance whether the model supports soft delete.
    """
    manager = getattr(model, "active_objects", None)
    if manager is not None:
        return manager.all()
    return model.objects.all()


def is_soft_deletable(model):
    """True if ``model`` supports soft delete (i.e. mixes in
    ``SoftDeleteModel``), without needing to import ``SoftDeleteModel`` at
    every call site to do an ``issubclass`` check by hand.
    """
    return hasattr(model, "active_objects") and hasattr(model, "is_deleted")


def touch(instance, *, updated_by=None):
    """Persist ``instance`` with ``updated_at`` advanced (if the model has
    one) and, optionally, ``updated_by`` stamped — without changing any
    other field.

    Useful for a future "mark as seen"/"bump" style operation that isn't a
    real business-field edit but should still count as "last touched now".
    Falls back to a plain ``save()`` for models without ``updated_at``
    (``auto_now`` already advances it on any save, so nothing extra is
    needed there either way).
    """
    if updated_by is not None and hasattr(instance, "updated_by"):
        instance.updated_by = updated_by
    instance.save()
    return instance


__all__ = [
    "soft_delete",
    "restore",
    "bulk_soft_delete",
    "bulk_restore",
    "stamp_audit_fields",
    "active_queryset",
    "is_soft_deletable",
    "touch",
]
