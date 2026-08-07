"""CP14: the activity layer — Task, Event, ActivityLog, Reminder.

Every model here inherits ``apps.core.models.SoftDeleteTimeStampedModel``
(CP7), exactly like every CP9+ domain model — an accidentally-deleted task
or a cancelled event should be reversibly removable, not permanently erased.

This is the first checkpoint where a model needs to attach to more than one
kind of CRM entity. `Task`/`Event`/`ActivityLog` can each optionally relate
to a `Customer`, `Lead`, `Opportunity` (``apps.crm``) or a `Quote`/`Invoice`
(``apps.sales``) — five different concrete models, none of which share a
common base class to hang a regular ForeignKey off. Rather than five
nullable FK columns per model (`customer`, `lead`, `opportunity`, `quote`,
`invoice` — four of which would always be NULL), this uses Django's
contenttypes framework: a `content_type` + `object_id` pair resolved
through `GenericForeignKey` into a single `related_object`. See
`RelatedToEntityModel` below.

`Reminder` is deliberately NOT generic to the five CRM entities directly —
a reminder only ever makes sense attached to a `Task` or an `Event` ("remind
me before this is due" / "remind me before this starts"), so it uses two
plain, specific nullable FKs instead, with an "exactly one of the two"
constraint — the same technique CP13's `PriceBookEntry` established for
"exactly one of product/service".
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteQuerySet, SoftDeleteTimeStampedModel

# --------------------------------------------------------------------------
# Shared "attach to a CRM entity" mixin
# --------------------------------------------------------------------------

#: The only content types a `Task`/`Event`/`ActivityLog` may point at — the
#: five CRM entities CP14 lists ("Customer, Lead, Opportunity, Quote,
#: Invoice"). Used as `limit_choices_to` so the admin's dropdown (and any
#: future form) only ever offers these five, not every model in the project.
RELATABLE_ENTITY_TYPES = Q(app_label="crm", model__in=["customer", "lead", "opportunity"]) | Q(
    app_label="sales", model__in=["quote", "invoice"]
)


class RelatedToEntityModel(models.Model):
    """Abstract mixin adding an optional generic link to one CRM entity.

    `content_type`/`object_id` are both nullable — not every `Task`/`Event`
    is necessarily about a specific customer/lead/deal (e.g. a personal
    "prepare Monday's report" to-do), so attachment is opt-in, not required.

    Each concrete subclass must declare its own `(content_type, object_id)`
    index with a model-specific name — deliberately NOT declared here, since
    an index name inherited unchanged from an abstract base would collide
    across tables (PostgreSQL index names are unique per-schema, not
    per-table).
    """

    content_type = models.ForeignKey(
        ContentType,
        verbose_name=_("related entity type"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        limit_choices_to=RELATABLE_ENTITY_TYPES,
        related_name="+",
    )
    object_id = models.PositiveBigIntegerField(_("related entity id"), null=True, blank=True)
    related_object = GenericForeignKey("content_type", "object_id")

    class Meta:
        abstract = True


# --------------------------------------------------------------------------
# Task
# --------------------------------------------------------------------------


class TaskQuerySet(SoftDeleteQuerySet):
    def for_entity(self, entity):
        content_type = ContentType.objects.get_for_model(entity)
        return self.filter(content_type=content_type, object_id=entity.pk)

    def open(self):
        return self.exclude(status__in=(Task.Status.COMPLETED, Task.Status.CANCELLED))


class TaskManager(models.Manager.from_queryset(TaskQuerySet)):
    """``Task.objects`` — unfiltered, per CP7's soft-delete convention."""


class ActiveTaskManager(TaskManager):
    def get_queryset(self):
        return super().get_queryset().active()


class Task(SoftDeleteTimeStampedModel, RelatedToEntityModel):
    class Priority(models.TextChoices):
        LOW = "LOW", _("Low")
        MEDIUM = "MEDIUM", _("Medium")
        HIGH = "HIGH", _("High")
        URGENT = "URGENT", _("Urgent")

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        IN_PROGRESS = "IN_PROGRESS", _("In Progress")
        COMPLETED = "COMPLETED", _("Completed")
        CANCELLED = "CANCELLED", _("Cancelled")

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_tasks",
        help_text=_("The user responsible for this task — used for ownership-based access scoping."),
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("assigned to"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
        help_text=_("The user this task is currently assigned to — may differ from owner."),
    )
    priority = models.CharField(
        _("priority"), max_length=10, choices=Priority.choices, default=Priority.MEDIUM, db_index=True
    )
    status = models.CharField(
        _("status"), max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    due_date = models.DateTimeField(_("due date"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)

    objects = TaskManager()
    active_objects = ActiveTaskManager()

    class Meta:
        ordering = ["due_date", "-priority"]
        verbose_name = _("task")
        verbose_name_plural = _("tasks")
        indexes = [
            models.Index(fields=["owner"], name="activities_task_owner_idx"),
            models.Index(fields=["assigned_to"], name="activities_task_assigned_idx"),
            models.Index(fields=["content_type", "object_id"], name="activities_task_entity_idx"),
        ]

    def __str__(self):
        return self.title

    def manager_has_access(self, user):
        """CP6's documented per-object extension point, reused unchanged —
        see ``apps.crm.models.Customer.manager_has_access()`` for the
        identical reasoning, applied to a `Task`'s own ``owner``.
        """
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# Event
# --------------------------------------------------------------------------


class EventQuerySet(SoftDeleteQuerySet):
    def for_entity(self, entity):
        content_type = ContentType.objects.get_for_model(entity)
        return self.filter(content_type=content_type, object_id=entity.pk)

    def upcoming(self):
        return self.filter(start_at__gte=timezone.now())


class EventManager(models.Manager.from_queryset(EventQuerySet)):
    """``Event.objects`` — unfiltered, per CP7's soft-delete convention."""


class ActiveEventManager(EventManager):
    def get_queryset(self):
        return super().get_queryset().active()


class Event(SoftDeleteTimeStampedModel, RelatedToEntityModel):
    class RecurrenceFrequency(models.TextChoices):
        NONE = "NONE", _("Does not repeat")
        DAILY = "DAILY", _("Daily")
        WEEKLY = "WEEKLY", _("Weekly")
        MONTHLY = "MONTHLY", _("Monthly")
        YEARLY = "YEARLY", _("Yearly")

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_events",
    )
    location = models.CharField(_("location"), max_length=255, blank=True, default="")
    start_at = models.DateTimeField(_("start at"))
    end_at = models.DateTimeField(_("end at"), null=True, blank=True)
    recurrence_frequency = models.CharField(
        _("recurrence frequency"),
        max_length=10,
        choices=RecurrenceFrequency.choices,
        default=RecurrenceFrequency.NONE,
        help_text=_("Basic recurrence only — a repeat frequency, not a full RFC 5545 RRULE."),
    )
    recurrence_end_date = models.DateField(
        _("recurrence end date"),
        null=True,
        blank=True,
        help_text=_("Last date occurrences are generated for. Ignored when recurrence_frequency is NONE."),
    )

    objects = EventManager()
    active_objects = ActiveEventManager()

    class Meta:
        ordering = ["start_at"]
        verbose_name = _("event")
        verbose_name_plural = _("events")
        constraints = [
            models.CheckConstraint(
                condition=Q(end_at__isnull=True) | Q(end_at__gte=models.F("start_at")),
                name="activities_event_end_after_start",
            ),
        ]
        indexes = [
            models.Index(fields=["owner"], name="activities_event_owner_idx"),
            models.Index(fields=["start_at"], name="activities_event_start_idx"),
            models.Index(fields=["content_type", "object_id"], name="activities_event_entity_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_at:%Y-%m-%d %H:%M})"

    @property
    def is_recurring(self):
        return self.recurrence_frequency != self.RecurrenceFrequency.NONE

    def manager_has_access(self, user):
        """See ``Task.manager_has_access()`` — identical reasoning."""
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# ActivityLog
# --------------------------------------------------------------------------


class ActivityLogQuerySet(SoftDeleteQuerySet):
    def for_entity(self, entity):
        content_type = ContentType.objects.get_for_model(entity)
        return self.filter(content_type=content_type, object_id=entity.pk)


class ActivityLogManager(models.Manager.from_queryset(ActivityLogQuerySet)):
    """``ActivityLog.objects`` — unfiltered, per CP7's soft-delete convention."""


class ActiveActivityLogManager(ActivityLogManager):
    def get_queryset(self):
        return super().get_queryset().active()


class ActivityLog(SoftDeleteTimeStampedModel, RelatedToEntityModel):
    """A logged, timestamped interaction against a CRM entity — a call, an
    email, a meeting, a note, or a status change. The generic counterpart to
    CP11's `OpportunityActivity` (which is Opportunity-specific); this
    checkpoint's version can log against any of the five CRM entities.
    """

    class ActivityType(models.TextChoices):
        NOTE = "NOTE", _("Note")
        CALL = "CALL", _("Call")
        EMAIL = "EMAIL", _("Email")
        MEETING = "MEETING", _("Meeting")
        STATUS_CHANGE = "STATUS_CHANGE", _("Status Change")
        OTHER = "OTHER", _("Other")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("actor"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
        help_text=_("The user who performed/logged this activity."),
    )
    activity_type = models.CharField(
        _("activity type"), max_length=20, choices=ActivityType.choices, default=ActivityType.OTHER, db_index=True
    )
    description = models.TextField(_("description"))
    occurred_at = models.DateTimeField(_("occurred at"), default=timezone.now, db_index=True)

    objects = ActivityLogManager()
    active_objects = ActiveActivityLogManager()

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = _("activity log")
        verbose_name_plural = _("activity logs")
        indexes = [
            models.Index(fields=["actor"], name="activities_log_actor_idx"),
            models.Index(fields=["content_type", "object_id"], name="activities_log_entity_idx"),
        ]

    def __str__(self):
        return f"{self.get_activity_type_display()} @ {self.occurred_at:%Y-%m-%d %H:%M}"

    @property
    def owner(self):
        """Lets ``IsOwnerOrSuperAdmin.resolve_owner()`` (CP6) find this log's
        owning user via its ``actor`` — an `ActivityLog` has no `owner` field
        of its own (`actor` is the more accurate name for "who logged this"),
        but access control should treat the actor as the owner. Same
        delegation pattern as CP9's ``ContactPerson.owner``.
        """
        return self.actor

    def manager_has_access(self, user):
        """See ``Task.manager_has_access()`` — identical reasoning, applied
        to this log's ``actor``.
        """
        from apps.crm.services import managed_user_ids

        return self.actor_id is not None and self.actor_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# Reminder
# --------------------------------------------------------------------------


class ReminderQuerySet(SoftDeleteQuerySet):
    def pending(self):
        return self.filter(is_sent=False)

    def due(self, *, as_of=None):
        as_of = as_of or timezone.now()
        return self.pending().filter(remind_at__lte=as_of)


class ReminderManager(models.Manager.from_queryset(ReminderQuerySet)):
    """``Reminder.objects`` — unfiltered, per CP7's soft-delete convention."""


class ActiveReminderManager(ReminderManager):
    def get_queryset(self):
        return super().get_queryset().active()


class Reminder(SoftDeleteTimeStampedModel):
    """A reminder for exactly one of a `Task` or an `Event` (never both,
    never neither — enforced by ``exactly_one_of_task_or_event`` below, the
    same technique CP13's `PriceBookEntry` established for "exactly one of
    product/service").
    """

    task = models.ForeignKey(
        Task,
        verbose_name=_("task"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    event = models.ForeignKey(
        Event,
        verbose_name=_("event"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    remind_at = models.DateTimeField(_("remind at"))
    message = models.CharField(_("message"), max_length=255, blank=True, default="")
    is_sent = models.BooleanField(_("is sent"), default=False, db_index=True)

    objects = ReminderManager()
    active_objects = ActiveReminderManager()

    class Meta:
        ordering = ["remind_at"]
        verbose_name = _("reminder")
        verbose_name_plural = _("reminders")
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(task__isnull=False) & Q(event__isnull=True))
                    | (Q(task__isnull=True) & Q(event__isnull=False))
                ),
                name="activities_reminder_exactly_one_of_task_or_event",
            ),
        ]
        indexes = [
            models.Index(fields=["remind_at", "is_sent"], name="activities_reminder_due_idx"),
        ]

    def __str__(self):
        subject = self.task or self.event
        return f"Reminder for {subject} @ {self.remind_at:%Y-%m-%d %H:%M}"

    @property
    def subject(self):
        """The `Task` or `Event` this reminder is for — whichever is set."""
        return self.task or self.event

    @property
    def owner(self):
        """Delegates to the owning `Task`/`Event`'s own ``owner`` — a
        `Reminder` has no owner of its own, "who may act on this reminder"
        follows whichever task/event it belongs to. Same delegation pattern
        as CP9's ``ContactPerson.owner``/``Address.owner``.
        """
        return self.subject.owner if self.subject is not None else None

    def manager_has_access(self, user):
        """Delegates to the owning `Task`/`Event`'s own hook — see
        ``Task.manager_has_access()``/``Event.manager_has_access()``.
        """
        return self.subject.manager_has_access(user) if self.subject is not None else False
