"""CP19: platform infrastructure — audit trail, settings, feature flags,
background job tracking.

`AuditLog` is the ONE model in this entire project that does NOT inherit
`SoftDeleteTimeStampedModel` — it inherits bare `TimeStampedModel`
instead, deliberately WITHOUT soft-delete support. An audit trail that
could be "soft-deleted" (even reversibly) is not a trustworthy audit
trail — CP7's `restore`/`hard-delete` actions must never apply to it, so
it doesn't get the mixin that would introduce them. See `views.py` for
how this is enforced at the API layer too (no destructive actions
exposed for this resource, at all).

`SystemSetting`/`FeatureFlag`/`BackgroundJob` are ordinary
`SoftDeleteTimeStampedModel` records — a mis-configured setting or a
disabled flag should be reversibly removable like any other record in
this project.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.activities.models import RelatedToEntityModel
from apps.core.models import SoftDeleteQuerySet, SoftDeleteTimeStampedModel, TimeStampedModel

# --------------------------------------------------------------------------
# AuditLog
# --------------------------------------------------------------------------


class AuditLogQuerySet(models.QuerySet):
    def for_actor(self, user):
        return self.filter(actor=user)

    def for_entity(self, entity):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(entity)
        return self.filter(content_type=content_type, object_id=entity.pk)


class AuditLog(TimeStampedModel, RelatedToEntityModel):
    """One recorded fact: "actor did action to entity, at this time."
    Written entirely by `services.log_audit_event()` — never by a client
    directly (no create endpoint; see `views.py`) — the same "system
    writes it, a client only reads it" integrity boundary CP15's
    `CommunicationLog`/CP16's `ReportExecution`/CP17's
    `WorkflowExecution`/CP18's `WebhookDelivery` all established, taken
    one step further here: NOT EVEN `restore`/`hard-delete` are exposed
    (see this module's own docstring for why).
    """

    class Action(models.TextChoices):
        CREATE = "CREATE", _("Create")
        UPDATE = "UPDATE", _("Update")
        DELETE = "DELETE", _("Delete")
        LOGIN = "LOGIN", _("Login")
        OTHER = "OTHER", _("Other")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("actor"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
        help_text=_("The user who performed this action, if known — null for system-triggered entries."),
    )
    action = models.CharField(_("action"), max_length=10, choices=Action.choices, db_index=True)
    description = models.TextField(_("description"), blank=True, default="")
    changes = models.JSONField(
        _("changes"), default=dict, blank=True,
        help_text=_("A snapshot of relevant field values at the time of this event — not a field-level diff (see BACKEND_LEARNING_GUIDE.md CP19)."),
    )
    ip_address = models.GenericIPAddressField(
        _("IP address"), null=True, blank=True,
        help_text=_("Only populated for API-request-triggered entries with request context available — see 'Deferred' in BACKEND_PROGRESS.md CP19."),
    )

    objects = models.Manager.from_queryset(AuditLogQuerySet)()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("audit log")
        verbose_name_plural = _("audit logs")
        indexes = [
            models.Index(fields=["actor"], name="system_auditlog_actor_idx"),
            models.Index(fields=["action"], name="system_auditlog_action_idx"),
            models.Index(fields=["content_type", "object_id"], name="system_auditlog_entity_idx"),
            # AuditLog is the one table in this project explicitly expected
            # to grow indefinitely and never be pruned (see this model's own
            # docstring — no restore/hard-delete either). Every unfiltered
            # list request pages through Meta.ordering's `-created_at`; the
            # other three indexes above only help once a filter is applied.
            # No other model in this project needs this same treatment —
            # they're all bounded by real-world business-record counts, not
            # an ever-growing event log.
            models.Index(fields=["-created_at"], name="system_auditlog_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_action_display()} by {self.actor or 'system'} @ {self.created_at:%Y-%m-%d %H:%M}"


# --------------------------------------------------------------------------
# SystemSetting
# --------------------------------------------------------------------------


class SystemSettingQuerySet(SoftDeleteQuerySet):
    def active(self):
        return super().active().filter(is_active=True)


class SystemSettingManager(models.Manager.from_queryset(SystemSettingQuerySet)):
    """``SystemSetting.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveSystemSettingManager(SystemSettingManager):
    def get_queryset(self):
        return super().get_queryset().active()


class SystemSetting(SoftDeleteTimeStampedModel):
    """A single named, typed-by-convention configuration value. `value` is
    a `JSONField` so ONE model can hold strings, numbers, booleans, lists,
    or objects without a column per type — the caller (``services.get_setting()``)
    is responsible for knowing what shape it expects back for a given
    `key`, the same "opaque, interpreted by convention" reasoning CP17's
    `WorkflowAction.configuration` already established.
    """

    key = models.CharField(_("key"), max_length=200, unique=True)
    value = models.JSONField(_("value"), default=dict, blank=True)
    description = models.TextField(_("description"), blank=True, default="")
    is_active = models.BooleanField(
        _("is active"), default=True, db_index=True,
        help_text=_("Business-status flag (e.g. retired setting), independent of soft delete."),
    )

    objects = SystemSettingManager()
    active_objects = ActiveSystemSettingManager()

    class Meta:
        ordering = ["key"]
        verbose_name = _("system setting")
        verbose_name_plural = _("system settings")

    def __str__(self):
        return self.key


# --------------------------------------------------------------------------
# FeatureFlag
# --------------------------------------------------------------------------


class FeatureFlagQuerySet(SoftDeleteQuerySet):
    def active(self):
        return super().active().filter(is_enabled=True)


class FeatureFlagManager(models.Manager.from_queryset(FeatureFlagQuerySet)):
    """``FeatureFlag.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveFeatureFlagManager(FeatureFlagManager):
    def get_queryset(self):
        return super().get_queryset().active()


class FeatureFlag(SoftDeleteTimeStampedModel):
    """A named on/off switch, with an OPTIONAL gradual-rollout percentage
    — see ``services.is_feature_enabled()`` for the evaluation logic
    (deterministic per-user hashing, not a fresh coin flip per call).
    """

    key = models.CharField(_("key"), max_length=200, unique=True)
    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")
    is_enabled = models.BooleanField(
        _("is enabled"), default=False, db_index=True,
        help_text=_("Master switch — a disabled flag is off for everyone regardless of rollout_percentage."),
    )
    rollout_percentage = models.PositiveSmallIntegerField(
        _("rollout percentage"), default=100,
        help_text=_("What percentage of users see this flag as enabled, once is_enabled=True. 100 means everyone."),
    )

    objects = FeatureFlagManager()
    active_objects = ActiveFeatureFlagManager()

    class Meta:
        ordering = ["key"]
        verbose_name = _("feature flag")
        verbose_name_plural = _("feature flags")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rollout_percentage__gte=0) & models.Q(rollout_percentage__lte=100),
                name="system_flag_rollout_pct_range",
            ),
        ]

    def __str__(self):
        return self.key


# --------------------------------------------------------------------------
# BackgroundJob
# --------------------------------------------------------------------------


class BackgroundJobQuerySet(SoftDeleteQuerySet):
    def by_owner(self, user):
        return self.filter(owner=user)


class BackgroundJobManager(models.Manager.from_queryset(BackgroundJobQuerySet)):
    """``BackgroundJob.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveBackgroundJobManager(BackgroundJobManager):
    def get_queryset(self):
        return super().get_queryset().active()


class BackgroundJob(SoftDeleteTimeStampedModel):
    """A TRACKING record for a background-style operation — this project
    has no actual task queue (no Celery/Redis — see `requirements.txt`'s
    own "LATER-only packages" note), so `BackgroundJob` records that an
    operation ran (or is running), it does not itself schedule or execute
    anything. The fourth appearance of the PENDING/RUNNING/COMPLETED/
    FAILED + `started_at`/`completed_at`/`result_data`/`error_message`
    shape this project has now used (`ReportExecution` CP16,
    `WorkflowExecution` CP17, `WebhookDelivery` CP18 — a different field
    name, `delivered_at`, but the same shape) — reused here rather than
    invented a fifth time.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        RUNNING = "RUNNING", _("Running")
        COMPLETED = "COMPLETED", _("Completed")
        FAILED = "FAILED", _("Failed")

    name = models.CharField(_("name"), max_length=200)
    job_type = models.CharField(_("job type"), max_length=100, db_index=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="background_jobs",
        help_text=_("The user who initiated this job, if known."),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    result_data = models.JSONField(_("result data"), default=dict, blank=True)
    error_message = models.TextField(_("error message"), blank=True, default="")

    objects = BackgroundJobManager()
    active_objects = ActiveBackgroundJobManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("background job")
        verbose_name_plural = _("background jobs")
        indexes = [
            models.Index(fields=["owner"], name="system_job_owner_idx"),
            models.Index(fields=["job_type", "status"], name="system_job_type_status_idx"),
        ]

    def __str__(self):
        return f"{self.name} [{self.status}]"

    def manager_has_access(self, user):
        """CP6's documented per-object extension point, reused unchanged
        — see ``apps.integrations.models.Integration.manager_has_access()``
        for the identical reasoning, applied to a `BackgroundJob`'s own
        ``owner``.
        """
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)
