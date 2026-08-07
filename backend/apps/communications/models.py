"""CP15: outbound communications — email templates/messages, in-app
notifications, and a unified cross-channel communication log.

    EmailTemplate --(rendered into)--> EmailMessage
    Notification                                       \\
    EmailMessage                                         >-- CommunicationLog
    (other channels, future)                            /

Every model inherits `apps.core.models.SoftDeleteTimeStampedModel` (CP7),
exactly like every CP9+ domain model.

`EmailMessage`/`Notification`/`CommunicationLog` reuse CP14's
`RelatedToEntityModel` mixin (`apps.activities.models`) UNCHANGED — the
identical `content_type`/`object_id`/`related_object` `GenericForeignKey`
shape, imported, not re-implemented, so an email or notification can
optionally reference the same five CRM entities (`Customer`, `Lead`,
`Opportunity`, `Quote`, `Invoice`) a `Task`/`Event`/`ActivityLog` can. This
is exactly the kind of cross-app reuse CP12 (`_CrmModelViewSet`) and CP14
itself (`managed_user_ids()`/`scope_queryset_for_user()`) already
established as this project's pattern for "don't duplicate logic that
already exists in a sibling app."
"""
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.activities.models import RelatedToEntityModel
from apps.core.models import SoftDeleteQuerySet, SoftDeleteTimeStampedModel

# --------------------------------------------------------------------------
# EmailTemplate
# --------------------------------------------------------------------------


class EmailTemplateQuerySet(SoftDeleteQuerySet):
    def active(self):
        return super().active().filter(is_active=True)


class EmailTemplateManager(models.Manager.from_queryset(EmailTemplateQuerySet)):
    """``EmailTemplate.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveEmailTemplateManager(EmailTemplateManager):
    def get_queryset(self):
        return super().get_queryset().active()


class EmailTemplate(SoftDeleteTimeStampedModel):
    """A reusable email subject/body pair with ``{{placeholder}}``
    substitution — see ``services.render_template()``. Deliberately NOT a
    full template-engine integration (no Django Template Language, no
    Jinja2): a CRM email template only ever needs simple field
    substitution (customer name, deal value, ...), and a full template
    engine would mean deciding how to sandbox arbitrary CRM data against
    autoescaping/security rules that a `{{name}}`-only substitution never
    raises in the first place.
    """

    name = models.CharField(_("name"), max_length=200, unique=True)
    subject = models.CharField(_("subject"), max_length=255)
    body = models.TextField(_("body"))
    is_active = models.BooleanField(
        _("is active"), default=True, db_index=True,
        help_text=_("Business-status flag (e.g. retired template), independent of soft delete."),
    )

    objects = EmailTemplateManager()
    active_objects = ActiveEmailTemplateManager()

    class Meta:
        ordering = ["name"]
        verbose_name = _("email template")
        verbose_name_plural = _("email templates")
        indexes = [
            models.Index(fields=["is_active"], name="comms_template_active_idx"),
        ]

    def __str__(self):
        return self.name


# --------------------------------------------------------------------------
# EmailMessage
# --------------------------------------------------------------------------


class EmailMessageQuerySet(SoftDeleteQuerySet):
    def for_entity(self, entity):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(entity)
        return self.filter(content_type=content_type, object_id=entity.pk)

    def queued(self):
        return self.filter(status=EmailMessage.Status.QUEUED)


class EmailMessageManager(models.Manager.from_queryset(EmailMessageQuerySet)):
    """``EmailMessage.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveEmailMessageManager(EmailMessageManager):
    def get_queryset(self):
        return super().get_queryset().active()


class EmailMessage(SoftDeleteTimeStampedModel, RelatedToEntityModel):
    """One outbound email — queued, then sent or failed.

    ``subject``/``body`` are a SNAPSHOT of the rendered content at
    queue-time, not a live re-render of ``template`` — so editing (or even
    deleting) a template later never retroactively changes what a
    historical `EmailMessage` record says was actually sent, the same
    "audit trail must reflect what actually happened" reasoning behind
    every prior checkpoint's soft-delete-over-hard-delete choice.
    """

    class Status(models.TextChoices):
        QUEUED = "QUEUED", _("Queued")
        SENT = "SENT", _("Sent")
        FAILED = "FAILED", _("Failed")

    template = models.ForeignKey(
        EmailTemplate,
        verbose_name=_("template"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="messages",
        help_text=_("The template this message was rendered from, if any — purely informational (see subject/body)."),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_email_messages",
        help_text=_("The user who queued this email — used for ownership-based access scoping."),
    )
    to_email = models.EmailField(_("to"))
    subject = models.CharField(_("subject"), max_length=255)
    body = models.TextField(_("body"))
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.QUEUED, db_index=True
    )
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)
    error_message = models.TextField(_("error message"), blank=True, default="")

    objects = EmailMessageManager()
    active_objects = ActiveEmailMessageManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("email message")
        verbose_name_plural = _("email messages")
        indexes = [
            models.Index(fields=["owner"], name="comms_email_owner_idx"),
            models.Index(fields=["status"], name="comms_email_status_idx"),
            models.Index(fields=["content_type", "object_id"], name="comms_email_entity_idx"),
        ]

    def __str__(self):
        return f"{self.subject} -> {self.to_email} [{self.status}]"

    def manager_has_access(self, user):
        """CP6's documented per-object extension point, reused unchanged —
        see ``apps.activities.models.Task.manager_has_access()`` for the
        identical reasoning, applied to an `EmailMessage`'s own ``owner``.
        """
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# Notification
# --------------------------------------------------------------------------


class NotificationQuerySet(SoftDeleteQuerySet):
    def unread(self):
        return self.filter(is_read=False)

    def for_recipient(self, user):
        return self.filter(recipient=user)


class NotificationManager(models.Manager.from_queryset(NotificationQuerySet)):
    """``Notification.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveNotificationManager(NotificationManager):
    def get_queryset(self):
        return super().get_queryset().active()


class Notification(SoftDeleteTimeStampedModel, RelatedToEntityModel):
    """An in-app notification for exactly one ``User`` (``recipient`` — not
    nullable: a notification for no one is meaningless, unlike every other
    "owner"-shaped field in this project, which is nullable).
    """

    class NotificationType(models.TextChoices):
        INFO = "INFO", _("Info")
        WARNING = "WARNING", _("Warning")
        ASSIGNMENT = "ASSIGNMENT", _("Assignment")
        REMINDER = "REMINDER", _("Reminder")
        SYSTEM = "SYSTEM", _("System")

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("recipient"),
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        _("notification type"), max_length=20, choices=NotificationType.choices, default=NotificationType.INFO,
        db_index=True,
    )
    title = models.CharField(_("title"), max_length=200)
    message = models.TextField(_("message"), blank=True, default="")
    is_read = models.BooleanField(_("is read"), default=False, db_index=True)
    read_at = models.DateTimeField(_("read at"), null=True, blank=True)

    objects = NotificationManager()
    active_objects = ActiveNotificationManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        indexes = [
            models.Index(fields=["recipient", "is_read"], name="comms_notif_recipient_read_idx"),
            models.Index(fields=["content_type", "object_id"], name="comms_notif_entity_idx"),
        ]

    def __str__(self):
        return self.title

    @property
    def owner(self):
        """Lets ``IsOwnerOrSuperAdmin.resolve_owner()`` (CP6) find this
        notification's owning user via ``recipient`` — a `Notification` has
        no ``owner`` field of its own (``recipient`` is the more accurate
        name), but access control should treat the recipient as the owner.
        Same delegation pattern as CP9's ``ContactPerson.owner``.
        """
        return self.recipient

    def manager_has_access(self, user):
        """See ``EmailMessage.manager_has_access()`` — identical reasoning,
        applied to this notification's ``recipient``.
        """
        from apps.crm.services import managed_user_ids

        return self.recipient_id is not None and self.recipient_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# CommunicationLog
# --------------------------------------------------------------------------


class CommunicationLogQuerySet(SoftDeleteQuerySet):
    def for_entity(self, entity):
        from django.contrib.contenttypes.models import ContentType

        content_type = ContentType.objects.get_for_model(entity)
        return self.filter(content_type=content_type, object_id=entity.pk)


class CommunicationLogManager(models.Manager.from_queryset(CommunicationLogQuerySet)):
    """``CommunicationLog.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveCommunicationLogManager(CommunicationLogManager):
    def get_queryset(self):
        return super().get_queryset().active()


class CommunicationLog(SoftDeleteTimeStampedModel, RelatedToEntityModel):
    """A unified, cross-channel audit trail entry — one row per actual
    communication touchpoint (an email sent/failed, a notification
    created, ...), written automatically by ``services.send_queued_email()``/
    ``services.create_notification()``, never by a client directly (there
    is no create endpoint for this model — see ``views.py``).

    Distinct from CP14's `ActivityLog`: `ActivityLog` is a human
    manually recording "I called them" / "I emailed them"; `CommunicationLog`
    is the SYSTEM's own record of a communication it actually sent/
    generated, written by this app's own services, not by a person. The
    two are not redundant — a salesperson's manual call note and the
    system's automatic "assignment email sent" record answer different
    questions and are populated by different code paths.
    """

    class Channel(models.TextChoices):
        EMAIL = "EMAIL", _("Email")
        NOTIFICATION = "NOTIFICATION", _("Notification")
        OTHER = "OTHER", _("Other")

    channel = models.CharField(_("channel"), max_length=20, choices=Channel.choices, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("actor"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="communication_logs",
        help_text=_("The user this communication was sent on behalf of, if known — null for system-triggered entries."),
    )
    summary = models.CharField(_("summary"), max_length=255)
    occurred_at = models.DateTimeField(_("occurred at"), default=timezone.now, db_index=True)

    objects = CommunicationLogManager()
    active_objects = ActiveCommunicationLogManager()

    class Meta:
        ordering = ["-occurred_at"]
        verbose_name = _("communication log")
        verbose_name_plural = _("communication logs")
        indexes = [
            models.Index(fields=["actor"], name="comms_log_actor_idx"),
            models.Index(fields=["content_type", "object_id"], name="comms_log_entity_idx"),
        ]

    def __str__(self):
        return f"[{self.channel}] {self.summary}"

    @property
    def owner(self):
        """See ``ActivityLog.owner`` (CP14) — identical delegation, applied
        to this log's ``actor``.
        """
        return self.actor

    def manager_has_access(self, user):
        """See ``EmailMessage.manager_has_access()`` — identical reasoning,
        applied to this log's ``actor``.
        """
        from apps.crm.services import managed_user_ids

        return self.actor_id is not None and self.actor_id in managed_user_ids(user)
