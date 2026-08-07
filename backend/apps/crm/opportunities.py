"""CP11: the sales pipeline — Opportunity, and the activities/notes logged
against it.

    Customer (CP9)
        \\-- Opportunity
                |-- OpportunityActivity
                \\-- OpportunityNote

Kept in its own module (rather than folded into ``models.py``) because it
is a genuinely separate sub-domain — pipeline/forecasting concerns, not
account/contact-record concerns — even though it imports ``Customer`` from
``models.py`` and is otherwise a peer of everything there. All three
models below inherit ``apps.core.models.SoftDeleteTimeStampedModel`` (CP7),
exactly like every other CP9+ CRM record — see BACKEND_LEARNING_GUIDE.md
CP9, "why soft delete now, when CP8 avoided it", which applies here too: a
lost opportunity or a mistakenly-logged activity should be reversibly
removable, not hard-deleted.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import ActiveManager, SoftDeleteManager, SoftDeleteQuerySet, SoftDeleteTimeStampedModel

from .models import Customer


class OpportunityQuerySet(SoftDeleteQuerySet):
    def by_stage(self, stage):
        return self.filter(stage=stage)

    def open(self):
        """Opportunities still moving through the pipeline (not WON/LOST)."""
        return self.filter(is_closed=False)

    def closed(self):
        """Opportunities that have reached WON or LOST."""
        return self.filter(is_closed=True)

    def won(self):
        return self.filter(is_won=True)

    def lost(self):
        """Closed, but not won — i.e. LOST specifically (not simply "not won
        yet", which would also match every still-open opportunity)."""
        return self.filter(is_closed=True, is_won=False)

    def high_value(self, threshold=10000):
        """Opportunities worth at least ``threshold`` (in ``value``'s own
        currency-less unit — see ``Opportunity.currency``'s docstring for
        why cross-currency comparison is explicitly out of scope here).
        """
        return self.filter(value__gte=threshold)

    def expected_this_month(self, today=None):
        """Opportunities whose ``expected_close_date`` falls within the
        current calendar month — the standard "what's forecast to close
        this month" pipeline view. ``today`` is injectable for testing
        (defaults to ``timezone.now().date()``); never comparing against a
        hardcoded date keeps this correct regardless of when it runs.
        """
        today = today or timezone.now().date()
        month_start = today.replace(day=1)
        if today.month == 12:
            next_month_start = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month_start = today.replace(month=today.month + 1, day=1)
        return self.filter(expected_close_date__gte=month_start, expected_close_date__lt=next_month_start)


class OpportunityManager(models.Manager.from_queryset(OpportunityQuerySet)):
    """``Opportunity.objects`` — unfiltered, per CP7's soft-delete manager
    convention.
    """


class ActiveOpportunityManager(OpportunityManager):
    """``Opportunity.active_objects`` — not-deleted only. Unlike
    ``Customer`` (CP9), `Opportunity` has no separate business "is_active"
    flag of its own — ``is_closed``/``is_won`` already fully describe its
    lifecycle, so "active" here means exactly what CP7's base
    ``SoftDeleteQuerySet.active()`` already means: not soft-deleted.
    """

    def get_queryset(self):
        return super().get_queryset().active()


class Opportunity(SoftDeleteTimeStampedModel):
    class Stage(models.TextChoices):
        NEW = "NEW", _("New")
        QUALIFIED = "QUALIFIED", _("Qualified")
        PROPOSAL = "PROPOSAL", _("Proposal")
        NEGOTIATION = "NEGOTIATION", _("Negotiation")
        WON = "WON", _("Won")
        LOST = "LOST", _("Lost")

    customer = models.ForeignKey(
        Customer,
        verbose_name=_("customer"),
        on_delete=models.CASCADE,
        related_name="opportunities",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_opportunities",
        help_text=_("The user (typically Manager-or-above) responsible for closing this deal."),
    )
    title = models.CharField(_("title"), max_length=200)
    stage = models.CharField(
        _("stage"), max_length=20, choices=Stage.choices, default=Stage.NEW, db_index=True
    )
    value = models.DecimalField(
        _("value"), max_digits=14, decimal_places=2, default=0,
        help_text=_("The deal's monetary value, in this opportunity's own `currency`."),
    )
    probability = models.PositiveSmallIntegerField(
        _("probability"), default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_("Estimated likelihood of winning, as a percentage (0-100)."),
    )
    expected_close_date = models.DateField(_("expected close date"), null=True, blank=True)
    actual_close_date = models.DateField(
        _("actual close date"), null=True, blank=True,
        help_text=_("Set automatically by mark_won()/mark_lost() — see apps.crm.services."),
    )
    currency = models.CharField(
        _("currency"), max_length=3, default="USD",
        help_text=_(
            "ISO 4217 currency code. `value` is stored as a plain decimal with no "
            "cross-currency conversion — comparing/aggregating `value` across "
            "opportunities with different `currency` values is the caller's "
            "responsibility, not something this model attempts to normalize."
        ),
    )
    description = models.TextField(_("description"), blank=True, default="")
    is_closed = models.BooleanField(
        _("is closed"), default=False, db_index=True,
        help_text=_("Set automatically by mark_won()/mark_lost()/reopen() — see apps.crm.services."),
    )
    is_won = models.BooleanField(
        _("is won"), default=False, db_index=True,
        help_text=_("Set automatically by mark_won()/mark_lost()/reopen() — see apps.crm.services."),
    )

    objects = OpportunityManager()
    active_objects = ActiveOpportunityManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("opportunity")
        verbose_name_plural = _("opportunities")
        indexes = [
            models.Index(fields=["customer", "stage"], name="crm_opp_customer_stage_idx"),
            models.Index(fields=["owner"], name="crm_opportunity_owner_idx"),
            models.Index(fields=["is_closed", "is_won"], name="crm_opp_closed_won_idx"),
            models.Index(fields=["expected_close_date"], name="crm_opp_expected_close_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.customer.name})"

    def manager_has_access(self, user):
        """See ``Customer.manager_has_access()`` (CP10) — identical
        reasoning, applied to an `Opportunity`'s own ``owner``. Reuses the
        SAME ``apps.crm.services.managed_user_ids()`` function CP10 already
        built, so an Opportunity's access rules can never drift from a
        Customer's or a Lead's.
        """
        from .services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


class OpportunityActivity(SoftDeleteTimeStampedModel):
    """A logged interaction (call, email, meeting, ...) against an
    ``Opportunity`` — the sales-activity timeline, distinct from
    ``OpportunityNote`` (free-text commentary, no structured type/timing).
    """

    class ActivityType(models.TextChoices):
        CALL = "CALL", _("Call")
        EMAIL = "EMAIL", _("Email")
        MEETING = "MEETING", _("Meeting")
        TASK = "TASK", _("Task")
        OTHER = "OTHER", _("Other")

    opportunity = models.ForeignKey(
        Opportunity,
        verbose_name=_("opportunity"),
        on_delete=models.CASCADE,
        related_name="activities",
    )
    activity_type = models.CharField(
        _("activity type"), max_length=20, choices=ActivityType.choices, default=ActivityType.OTHER, db_index=True
    )
    subject = models.CharField(_("subject"), max_length=200)
    notes = models.TextField(_("notes"), blank=True, default="")
    occurred_at = models.DateTimeField(_("occurred at"), default=timezone.now)

    objects = SoftDeleteManager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = _("opportunity activity")
        verbose_name_plural = _("opportunity activities")
        indexes = [
            models.Index(fields=["opportunity", "occurred_at"], name="crm_opp_activity_occurred_idx"),
        ]

    def __str__(self):
        return f"{self.get_activity_type_display()}: {self.subject}"

    @property
    def owner(self):
        """See ``ContactPerson.owner``/``Address.owner`` (CP9) — same
        "belongs to an owned parent" delegation pattern.
        """
        return self.opportunity.owner

    def manager_has_access(self, user):
        """Delegates to the parent ``Opportunity``'s own hook."""
        return self.opportunity.manager_has_access(user)


class OpportunityNote(SoftDeleteTimeStampedModel):
    """Free-text commentary logged against an ``Opportunity`` — who wrote
    it and when is already covered by the inherited ``created_by``/
    ``created_at`` (CP7); this model itself only needs the text.
    """

    opportunity = models.ForeignKey(
        Opportunity,
        verbose_name=_("opportunity"),
        on_delete=models.CASCADE,
        related_name="notes",
    )
    content = models.TextField(_("content"))

    objects = SoftDeleteManager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("opportunity note")
        verbose_name_plural = _("opportunity notes")
        indexes = [
            models.Index(fields=["opportunity"], name="crm_opportunity_note_opp_idx"),
        ]

    def __str__(self):
        preview = self.content[:50]
        return preview + ("…" if len(self.content) > 50 else "")

    @property
    def owner(self):
        """See ``OpportunityActivity.owner`` — same delegation pattern."""
        return self.opportunity.owner

    def manager_has_access(self, user):
        """Delegates to the parent ``Opportunity``'s own hook."""
        return self.opportunity.manager_has_access(user)
