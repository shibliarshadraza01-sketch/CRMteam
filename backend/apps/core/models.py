"""CP7: reusable abstract base models for the entire CRM domain.

Every future business model (Lead, Customer, Payment, ...) is expected to
inherit from one of the three concrete-facing abstract models below rather
than re-declaring timestamps, soft-delete, or audit fields by hand:

- ``TimeStampedModel``           — ``created_at`` / ``updated_at`` only.
- ``SoftDeleteModel``             — ``is_deleted`` / ``deleted_at`` only.
- ``SoftDeleteTimeStampedModel``  — both, the model most future domain
                                     models are expected to actually use.

All three also carry ``created_by`` / ``updated_by`` (see ``AuditModel``
below) — CP7's spec requires every base model to support audit fields, in
preparation for a future middleware that stamps them automatically from
``request.user`` (see "Designed for future middleware" in the module
docstrings below; that middleware is explicitly OUT of scope for CP7).

See BACKEND_LEARNING_GUIDE.md CP7, "why abstract models exist" and "soft
delete architecture", for the full design rationale — including why the
three-class diamond below (``SoftDeleteTimeStampedModel`` inheriting from
both ``TimeStampedModel`` and ``SoftDeleteModel``, which both in turn
inherit from the same ``AuditModel``) is safe in Django rather than a field
clash, and why the manager setup below survives that same diamond correctly.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AuditModel(models.Model):
    """Abstract base providing ``created_by`` / ``updated_by``.

    Deliberately its own abstract class (rather than fields duplicated onto
    ``TimeStampedModel`` and ``SoftDeleteModel`` independently) so that
    ``SoftDeleteTimeStampedModel``, which inherits from both, gets exactly
    ONE copy of each audit field rather than a Django field-name clash — see
    BACKEND_LEARNING_GUIDE.md CP7 for why this specific shape was verified
    safe before being relied on.

    Both fields are nullable: a record can exist with no known actor (e.g.
    a data migration, a system-generated row, or simply because no
    authenticated request created it) — this is intentionally NOT a
    required field. Neither field is ``editable`` through a ModelForm/admin
    form field by default; they are meant to be set by code (a future
    middleware, or the utilities in ``apps/core/utils.py``), not typed in
    by a user.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("created by"),
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_created",
        help_text=_("The user who created this record, if known."),
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("updated by"),
        null=True,
        blank=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="%(app_label)s_%(class)s_updated",
        help_text=_("The user who last updated this record, if known."),
    )

    class Meta:
        abstract = True


class TimeStampedModel(AuditModel):
    """Abstract base providing ``created_at`` / ``updated_at`` (+ audit).

    ``created_at`` is set once, at creation (``auto_now_add``).
    ``updated_at`` advances on every ``save()`` (``auto_now``) — including a
    soft delete or restore, both of which call ``save()`` (see
    ``SoftDeleteModel`` below), so ``updated_at`` always reflects the most
    recent change of any kind, not just "business field" edits.
    """

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet powering both of ``SoftDeleteModel``'s managers.

    Chainable, so ``Model.objects.deleted().order_by(...)`` etc. work
    exactly like any other queryset method.
    """

    def active(self):
        """Rows not (soft-)deleted."""
        return self.filter(is_deleted=False)

    def deleted(self):
        """Only rows that ARE (soft-)deleted."""
        return self.filter(is_deleted=True)

    def delete(self):
        """Bulk **soft** delete every row in this queryset.

        Overrides ``QuerySet.delete()`` deliberately: CP7's spec is explicit
        that "No permanent delete unless explicitly requested" — calling
        ``.delete()`` on a queryset of soft-deletable rows must not silently
        perform a real SQL DELETE. Callers who genuinely want a permanent
        delete must call ``.hard_delete()`` instead, an intentionally
        differently-named method so it can never be reached by accident.

        Returns the number of rows updated, mirroring (not identical to,
        since there's no per-model breakdown) the ``(count, {model: count})``
        shape Django's real ``delete()`` returns, so callers checking "how
        many were affected" still get a usable number.
        """
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """Permanently delete every row in this queryset from the database.

        The ONLY way to actually remove soft-deletable rows via a queryset —
        named differently from ``delete()`` on purpose, see that method's
        docstring.
        """
        return super().delete()

    def restore(self):
        """Bulk-restore every (soft-)deleted row in this queryset."""
        return self.update(is_deleted=False, deleted_at=None)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """The default manager for soft-deletable models: ``objects``.

    Deliberately UNFILTERED — returns every row, deleted or not. This is
    what lets an admin (or a future "trash" view) find and restore a
    soft-deleted row at all: if ``objects`` excluded deleted rows, there
    would be no manager left to look them up by. Use ``active_objects``
    (below) wherever "the normal, non-deleted rows" is what's actually
    wanted — which is most call sites.
    """


class ActiveManager(SoftDeleteManager):
    """``active_objects`` — the common case: only non-deleted rows.

    Reuses ``SoftDeleteManager``'s full queryset API (``.deleted()``,
    ``.hard_delete()``, etc. all still work), just pre-filtered.
    """

    def get_queryset(self):
        return super().get_queryset().active()


class SoftDeleteModel(AuditModel):
    """Abstract base providing soft delete (+ audit).

    A "soft-deleted" row is never removed from the database — it is marked
    ``is_deleted=True`` with a ``deleted_at`` timestamp and left in place.
    This is a deliberate, permanent policy for this checkpoint: "No
    permanent delete unless explicitly requested" (CP7 spec) — the only way
    to truly remove a row is the explicitly, differently-named
    ``hard_delete()`` (instance method, below, or the queryset/manager
    method of the same name).

    Two managers are provided (see their own docstrings): ``objects``
    (unfiltered — everything, deleted or not) and ``active_objects``
    (non-deleted only). ``objects`` is deliberately the DEFAULT manager
    (Django uses the first manager defined, in MRO order, as a model's
    implicit default for things like related-object access) so that
    relations and admin lookups are never silently hidden — a future
    developer who forgets soft delete exists and just writes
    ``SomeModel.objects.get(pk=...)`` will still find a soft-deleted row
    rather than getting a confusing "does not exist".
    """

    is_deleted = models.BooleanField(_("is deleted"), default=False, db_index=True)
    deleted_at = models.DateTimeField(_("deleted at"), null=True, blank=True)

    objects = SoftDeleteManager()
    active_objects = ActiveManager()

    class Meta:
        abstract = True

    def soft_delete(self, *, updated_by=None, using=None):
        """Mark this instance deleted without removing it from the database.

        A plain, full ``save()`` (not a restricted ``update_fields`` save):
        this method is defined on an abstract class combined in different
        concrete shapes (with or without ``TimeStampedModel`` alongside it),
        so restricting ``update_fields`` to a fixed list here would silently
        stop ``updated_at`` (when present) from advancing. A full save is
        simpler and correct in every combination.
        """
        self.is_deleted = True
        self.deleted_at = timezone.now()
        if updated_by is not None:
            self.updated_by = updated_by
        self.save(using=using)

    def restore(self, *, updated_by=None, using=None):
        """Reverse ``soft_delete()`` — clears ``is_deleted``/``deleted_at``."""
        self.is_deleted = False
        self.deleted_at = None
        if updated_by is not None:
            self.updated_by = updated_by
        self.save(using=using)

    def hard_delete(self, using=None, keep_parents=False):
        """Permanently remove this single instance from the database.

        Named differently from ``delete()`` deliberately — this class does
        NOT override ``Model.delete()`` at the instance level (unlike
        ``SoftDeleteQuerySet.delete()``, which does), so
        ``some_instance.delete()`` still performs Django's normal hard
        delete by default. Instance-level soft delete is opt-in and
        explicit (``instance.soft_delete()``), never triggered implicitly
        by code that just calls the standard ``.delete()`` on an instance
        it received from elsewhere — see BACKEND_LEARNING_GUIDE.md CP7,
        "why the instance-level delete() is NOT overridden", for the reason
        this differs from the queryset-level override above.
        """
        return super().delete(using=using, keep_parents=keep_parents)


class SoftDeleteTimeStampedModel(TimeStampedModel, SoftDeleteModel):
    """The base most future domain models (Lead, Customer, ...) are expected
    to actually inherit from: timestamps + soft delete + audit fields, all
    in one class.

    See BACKEND_LEARNING_GUIDE.md CP7 for why this multiple-inheritance
    "diamond" (both parents ultimately inheriting ``AuditModel``) is safe
    here rather than a Django field clash, and why ``objects``/
    ``active_objects`` still resolve to ``SoftDeleteModel``'s managers
    despite ``TimeStampedModel`` appearing first in the MRO.
    """

    class Meta:
        abstract = True
