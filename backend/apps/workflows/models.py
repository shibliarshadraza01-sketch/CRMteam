"""CP17: workflow automation — trigger + action rules and their runs.

    Workflow --< WorkflowTrigger
             --< WorkflowAction
             --< WorkflowExecution

Every model inherits `apps.core.models.SoftDeleteTimeStampedModel` (CP7).
`Workflow` has a real `owner` FK (CP10's ownership-scoping model applies
directly). `WorkflowTrigger`/`WorkflowAction`/`WorkflowExecution` have no
owner of their own — each delegates via an `owner` PROPERTY to the
`Workflow` they belong to, the same pattern CP9's `ContactPerson.owner`
established and every checkpoint since has reused.

`WorkflowExecution` reuses CP14's `RelatedToEntityModel` mixin
(`apps.activities.models`) UNCHANGED — a workflow run is always ABOUT a
specific CRM entity instance (the `Lead` that was created, the
`Opportunity` that changed stage), the same "attach to one of five CRM
entities via GenericForeignKey" shape CP15's `EmailMessage`/`Notification`
already reuse.

`WorkflowTrigger` needs a DIFFERENT, narrower shape: it watches a MODEL
TYPE ("fire when any Lead is created"), not one specific row — so it
holds a bare `content_type` FK (no `object_id`), reusing the same
`RELATABLE_ENTITY_TYPES` constant `RelatedToEntityModel` limits its own
`content_type` field to, for the identical "only these five CRM entities"
reasoning, without pulling in `RelatedToEntityModel`'s `object_id`/
`GenericForeignKey` (which would be meaningless for "any row of this
type").
"""
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.activities.models import RELATABLE_ENTITY_TYPES, RelatedToEntityModel
from apps.core.models import SoftDeleteQuerySet, SoftDeleteTimeStampedModel

# --------------------------------------------------------------------------
# Workflow
# --------------------------------------------------------------------------


class WorkflowQuerySet(SoftDeleteQuerySet):
    def active(self):
        return super().active().filter(is_active=True)

    def by_owner(self, user):
        return self.filter(owner=user)


class WorkflowManager(models.Manager.from_queryset(WorkflowQuerySet)):
    """``Workflow.objects`` — unfiltered, per CP7's soft-delete convention."""


class ActiveWorkflowManager(WorkflowManager):
    def get_queryset(self):
        return super().get_queryset().active()


class Workflow(SoftDeleteTimeStampedModel):
    """A named automation: when its `triggers` match, its `actions` run,
    in `position` order, and the run is recorded as a `WorkflowExecution`.
    """

    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_workflows",
    )
    is_active = models.BooleanField(
        _("is active"), default=True, db_index=True,
        help_text=_("Business-status flag (e.g. paused automation), independent of soft delete."),
    )

    objects = WorkflowManager()
    active_objects = ActiveWorkflowManager()

    class Meta:
        ordering = ["name"]
        verbose_name = _("workflow")
        verbose_name_plural = _("workflows")
        indexes = [
            models.Index(fields=["owner"], name="workflows_workflow_owner_idx"),
        ]

    def __str__(self):
        return self.name

    def manager_has_access(self, user):
        """CP6's documented per-object extension point, reused unchanged —
        see ``apps.reports.models.SavedReport.manager_has_access()`` for
        the identical reasoning, applied to a `Workflow`'s own ``owner``.
        """
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# WorkflowTrigger
# --------------------------------------------------------------------------


class WorkflowTriggerQuerySet(SoftDeleteQuerySet):
    def for_workflow(self, workflow):
        return self.filter(workflow=workflow)

    def for_entity_type(self, model):
        return self.filter(content_type=ContentType.objects.get_for_model(model))


class WorkflowTriggerManager(models.Manager.from_queryset(WorkflowTriggerQuerySet)):
    """``WorkflowTrigger.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveWorkflowTriggerManager(WorkflowTriggerManager):
    def get_queryset(self):
        return super().get_queryset().active()


class WorkflowTrigger(SoftDeleteTimeStampedModel):
    """What starts a `Workflow` running: an event type (``trigger_type``),
    optionally narrowed to one entity TYPE (``content_type`` — e.g. "any
    Lead") and further narrowed by simple ``conditions``.

    No Django signal is actually wired to any CRM model to fire these
    automatically (see `services.py`'s module docstring for why) — a
    `WorkflowTrigger` today is evaluated only when a caller explicitly
    asks (``services.evaluate_and_run()``), which is exactly what
    ``WorkflowViewSet.execute`` (an authenticated, deliberate API call)
    does. ``MANUAL`` is the only trigger type this checkpoint's own API
    actually exercises end-to-end; ``ON_CREATE``/``ON_UPDATE``/``ON_DELETE``
    are modeled and evaluable today, ready for a future signal receiver to
    call the same evaluation function.
    """

    class TriggerType(models.TextChoices):
        ON_CREATE = "ON_CREATE", _("On Create")
        ON_UPDATE = "ON_UPDATE", _("On Update")
        ON_DELETE = "ON_DELETE", _("On Delete")
        MANUAL = "MANUAL", _("Manual")

    workflow = models.ForeignKey(
        Workflow,
        verbose_name=_("workflow"),
        on_delete=models.CASCADE,
        related_name="triggers",
    )
    trigger_type = models.CharField(
        _("trigger type"), max_length=10, choices=TriggerType.choices, default=TriggerType.MANUAL, db_index=True
    )
    content_type = models.ForeignKey(
        ContentType,
        verbose_name=_("entity type"),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        limit_choices_to=RELATABLE_ENTITY_TYPES,
        related_name="+",
        help_text=_("Which CRM entity type this trigger watches — e.g. 'any Lead'. Null for a type-agnostic MANUAL trigger."),
    )
    conditions = models.JSONField(
        _("conditions"), default=dict, blank=True,
        help_text=_("A simple {'field': ..., 'equals': ...} check against the entity — see services.evaluate_conditions(). Empty means 'always match'."),
    )

    objects = WorkflowTriggerManager()
    active_objects = ActiveWorkflowTriggerManager()

    class Meta:
        ordering = ["workflow", "id"]
        verbose_name = _("workflow trigger")
        verbose_name_plural = _("workflow triggers")
        indexes = [
            models.Index(fields=["content_type"], name="workflows_trigger_entity_idx"),
        ]

    def __str__(self):
        return f"{self.workflow.name} / {self.get_trigger_type_display()}"

    @property
    def owner(self):
        """See `models.py`'s module docstring — delegates to the owning
        `Workflow`.
        """
        return self.workflow.owner

    def manager_has_access(self, user):
        """Delegates to the owning ``Workflow``'s own hook."""
        return self.workflow.manager_has_access(user)


# --------------------------------------------------------------------------
# WorkflowAction
# --------------------------------------------------------------------------


class WorkflowActionQuerySet(SoftDeleteQuerySet):
    def for_workflow(self, workflow):
        return self.filter(workflow=workflow).order_by("position")


class WorkflowActionManager(models.Manager.from_queryset(WorkflowActionQuerySet)):
    """``WorkflowAction.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveWorkflowActionManager(WorkflowActionManager):
    def get_queryset(self):
        return super().get_queryset().active()


class WorkflowAction(SoftDeleteTimeStampedModel):
    """One step of a `Workflow` — what to actually DO when it runs, in
    `position` order. ``configuration`` is action-type-specific — see
    ``services.py``'s dispatch table for the shape each `action_type`
    expects.
    """

    class ActionType(models.TextChoices):
        SEND_EMAIL = "SEND_EMAIL", _("Send Email")
        CREATE_TASK = "CREATE_TASK", _("Create Task")
        CREATE_NOTIFICATION = "CREATE_NOTIFICATION", _("Create Notification")
        LOG_ACTIVITY = "LOG_ACTIVITY", _("Log Activity")

    workflow = models.ForeignKey(
        Workflow,
        verbose_name=_("workflow"),
        on_delete=models.CASCADE,
        related_name="actions",
    )
    action_type = models.CharField(_("action type"), max_length=20, choices=ActionType.choices, db_index=True)
    configuration = models.JSONField(
        _("configuration"), default=dict, blank=True,
        help_text=_("Action-type-specific parameters — interpreted by services.py's dispatch table."),
    )
    position = models.PositiveIntegerField(_("position"), default=0)

    objects = WorkflowActionManager()
    active_objects = ActiveWorkflowActionManager()

    class Meta:
        ordering = ["workflow", "position"]
        verbose_name = _("workflow action")
        verbose_name_plural = _("workflow actions")
        indexes = [
            models.Index(fields=["workflow", "position"], name="workflows_action_position_idx"),
        ]

    def __str__(self):
        return f"{self.workflow.name} / {self.get_action_type_display()}"

    @property
    def owner(self):
        """See `WorkflowTrigger.owner` — identical delegation."""
        return self.workflow.owner

    def manager_has_access(self, user):
        """Delegates to the owning ``Workflow``'s own hook."""
        return self.workflow.manager_has_access(user)


# --------------------------------------------------------------------------
# WorkflowExecution
# --------------------------------------------------------------------------


class WorkflowExecutionQuerySet(SoftDeleteQuerySet):
    def for_workflow(self, workflow):
        return self.filter(workflow=workflow)


class WorkflowExecutionManager(models.Manager.from_queryset(WorkflowExecutionQuerySet)):
    """``WorkflowExecution.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveWorkflowExecutionManager(WorkflowExecutionManager):
    def get_queryset(self):
        return super().get_queryset().active()


class WorkflowExecution(SoftDeleteTimeStampedModel, RelatedToEntityModel):
    """One run of a `Workflow` against one entity — created and driven
    entirely by ``services.run_workflow()``; there is no create endpoint
    (see ``views.py``), the same "system writes it, a client only reads
    it" integrity boundary CP15's `CommunicationLog`/CP16's
    `ReportExecution` established.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        RUNNING = "RUNNING", _("Running")
        COMPLETED = "COMPLETED", _("Completed")
        FAILED = "FAILED", _("Failed")

    workflow = models.ForeignKey(
        Workflow,
        verbose_name=_("workflow"),
        on_delete=models.CASCADE,
        related_name="executions",
    )
    trigger = models.ForeignKey(
        WorkflowTrigger,
        verbose_name=_("trigger"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="executions",
        help_text=_("Which trigger started this run, if any — null for a manually-invoked run with no matched trigger."),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    result_data = models.JSONField(
        _("result data"), default=dict, blank=True,
        help_text=_("Per-action outcomes — see services.run_workflow()."),
    )
    error_message = models.TextField(_("error message"), blank=True, default="")

    objects = WorkflowExecutionManager()
    active_objects = ActiveWorkflowExecutionManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("workflow execution")
        verbose_name_plural = _("workflow executions")
        indexes = [
            models.Index(fields=["workflow", "status"], name="workflows_exec_status_idx"),
            models.Index(fields=["content_type", "object_id"], name="workflows_exec_entity_idx"),
        ]

    def __str__(self):
        return f"{self.workflow.name} [{self.status}] @ {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def owner(self):
        """See `WorkflowTrigger.owner` — identical delegation."""
        return self.workflow.owner

    def manager_has_access(self, user):
        """Delegates to the owning ``Workflow``'s own hook."""
        return self.workflow.manager_has_access(user)
