"""CP18: external integrations — API keys and outbound webhooks.

    Integration --< APIKey
                --< WebhookEndpoint --< WebhookDelivery

Every model inherits `apps.core.models.SoftDeleteTimeStampedModel` (CP7).
`Integration` has a real `owner` FK; `APIKey`/`WebhookEndpoint` delegate
`owner` to `integration.owner`, and `WebhookDelivery` delegates two levels
deep to `endpoint.integration.owner` — the same multi-level delegation
chain CP14's `Reminder.owner` (-> `Task`/`Event`.owner) already
established.

Two DELIBERATELY DIFFERENT secret-storage strategies live in this file,
for two DIFFERENT kinds of secret — see `APIKey`'s and `WebhookEndpoint`'s
own docstrings for why storing them the same way would be wrong for one
of the two.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import SoftDeleteQuerySet, SoftDeleteTimeStampedModel

# --------------------------------------------------------------------------
# Integration
# --------------------------------------------------------------------------


class IntegrationQuerySet(SoftDeleteQuerySet):
    def active(self):
        return super().active().filter(is_active=True)

    def by_owner(self, user):
        return self.filter(owner=user)


class IntegrationManager(models.Manager.from_queryset(IntegrationQuerySet)):
    """``Integration.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveIntegrationManager(IntegrationManager):
    def get_queryset(self):
        return super().get_queryset().active()


class Integration(SoftDeleteTimeStampedModel):
    """A named external integration (e.g. "Zapier", "Internal Reporting
    Tool") that a set of `APIKey`s and `WebhookEndpoint`s belong to.
    """

    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_integrations",
    )
    is_active = models.BooleanField(
        _("is active"), default=True, db_index=True,
        help_text=_("Business-status flag (e.g. suspended integration), independent of soft delete."),
    )

    objects = IntegrationManager()
    active_objects = ActiveIntegrationManager()

    class Meta:
        ordering = ["name"]
        verbose_name = _("integration")
        verbose_name_plural = _("integrations")
        indexes = [
            models.Index(fields=["owner"], name="integrations_owner_idx"),
        ]

    def __str__(self):
        return self.name

    def manager_has_access(self, user):
        """CP6's documented per-object extension point, reused unchanged —
        see ``apps.workflows.models.Workflow.manager_has_access()`` for
        the identical reasoning, applied to an `Integration`'s own
        ``owner``.
        """
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# APIKey
# --------------------------------------------------------------------------


class APIKeyQuerySet(SoftDeleteQuerySet):
    def active(self):
        return super().active().filter(is_active=True, revoked_at__isnull=True)

    def for_integration(self, integration):
        return self.filter(integration=integration)


class APIKeyManager(models.Manager.from_queryset(APIKeyQuerySet)):
    """``APIKey.objects`` — unfiltered, per CP7's soft-delete convention."""


class ActiveAPIKeyManager(APIKeyManager):
    def get_queryset(self):
        return super().get_queryset().active()


class APIKey(SoftDeleteTimeStampedModel):
    """A bearer credential a caller presents TO this API. Stored the same
    way CP4's `User.super_admin_access_code_hash` stores its secondary
    access code: as a Django password HASH (`key_hash`, via
    `django.contrib.auth.hashers.make_password()`/`check_password()`),
    never the raw key. This is a deliberate reuse of EXISTING project
    infrastructure, not a new hashing scheme — see `services.py`.

    `key_prefix` (a short, non-secret slice of the raw key, e.g.
    ``clk_a1b2c3d4``) is stored in PLAINTEXT and is safe to display in a
    UI/list endpoint — it lets an owner recognize WHICH key a row is
    without ever re-deriving the secret, the same "prefix visible, rest
    hashed" convention Stripe/GitHub/AWS all use for their own API keys.

    The RAW key itself is returned to the caller exactly ONCE, at
    generation/rotation time (see `services.generate_api_key()`/
    `rotate_api_key()`) — it is never persisted anywhere in recoverable
    form and can never be displayed again after that single response.
    """

    integration = models.ForeignKey(
        Integration,
        verbose_name=_("integration"),
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(_("name"), max_length=200, help_text=_("A human label, e.g. 'Production key'."))
    key_prefix = models.CharField(_("key prefix"), max_length=16, unique=True)
    key_hash = models.CharField(_("key hash"), max_length=128)
    is_active = models.BooleanField(_("is active"), default=True, db_index=True)
    last_used_at = models.DateTimeField(_("last used at"), null=True, blank=True)
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)

    objects = APIKeyManager()
    active_objects = ActiveAPIKeyManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("API key")
        verbose_name_plural = _("API keys")
        indexes = [
            models.Index(fields=["integration"], name="integrations_apikey_integ_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.key_prefix})"

    @property
    def owner(self):
        """See `models.py`'s module docstring — delegates to the owning
        `Integration`.
        """
        return self.integration.owner

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        from django.utils import timezone

        return timezone.now() >= self.expires_at

    @property
    def is_revoked(self):
        return self.revoked_at is not None

    def manager_has_access(self, user):
        """Delegates to the owning ``Integration``'s own hook."""
        return self.integration.manager_has_access(user)


# --------------------------------------------------------------------------
# WebhookEndpoint
# --------------------------------------------------------------------------


class WebhookEndpointQuerySet(SoftDeleteQuerySet):
    def active(self):
        return super().active().filter(is_active=True)

    def for_integration(self, integration):
        return self.filter(integration=integration)

    def subscribed_to(self, event_type):
        return self.filter(event_types__contains=[event_type])


class WebhookEndpointManager(models.Manager.from_queryset(WebhookEndpointQuerySet)):
    """``WebhookEndpoint.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveWebhookEndpointManager(WebhookEndpointManager):
    def get_queryset(self):
        return super().get_queryset().active()


class WebhookEndpoint(SoftDeleteTimeStampedModel):
    """Where this API sends outbound event notifications, and what it
    signs them with.

    Unlike `APIKey.key_hash`, `secret` is stored in PLAINTEXT — a
    deliberate, DIFFERENT choice for a DIFFERENT kind of secret. An API
    key is a credential presented TO us; we only ever need to VERIFY it,
    so hashing (one-way) is correct and strictly more secure. A webhook
    secret is used BY us to SIGN outbound payloads (HMAC — see
    `services.sign_payload()`), and the endpoint's owner may legitimately
    need to view/copy it again later (e.g. configuring signature
    verification on a new receiving server) — the same UX real webhook
    providers (Stripe, GitHub) offer for their own webhook signing
    secrets, which are shown in their dashboards indefinitely, unlike
    their API keys. Encrypting this field at rest (rather than storing it
    in plaintext in the database) would be a genuine hardening
    improvement this checkpoint does not build — see
    BACKEND_LEARNING_GUIDE.md CP18 and this project's "Deferred" notes
    for why that's an honest, explicit gap rather than a hidden one.
    """

    integration = models.ForeignKey(
        Integration,
        verbose_name=_("integration"),
        on_delete=models.CASCADE,
        related_name="webhook_endpoints",
    )
    url = models.URLField(_("url"))
    secret = models.CharField(_("secret"), max_length=128)
    event_types = models.JSONField(
        _("event types"), default=list, blank=True,
        help_text=_("Which event type strings (e.g. 'lead.created') this endpoint receives. Empty means all."),
    )
    is_active = models.BooleanField(_("is active"), default=True, db_index=True)

    objects = WebhookEndpointManager()
    active_objects = ActiveWebhookEndpointManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("webhook endpoint")
        verbose_name_plural = _("webhook endpoints")
        indexes = [
            models.Index(fields=["integration"], name="integrations_webhook_integ_idx"),
        ]

    def __str__(self):
        return self.url

    @property
    def owner(self):
        """See `APIKey.owner` — identical delegation."""
        return self.integration.owner

    def manager_has_access(self, user):
        """Delegates to the owning ``Integration``'s own hook."""
        return self.integration.manager_has_access(user)


# --------------------------------------------------------------------------
# WebhookDelivery
# --------------------------------------------------------------------------


class WebhookDeliveryQuerySet(SoftDeleteQuerySet):
    def for_endpoint(self, endpoint):
        return self.filter(endpoint=endpoint)

    def due_for_retry(self, *, as_of=None):
        from django.utils import timezone

        as_of = as_of or timezone.now()
        return self.filter(status=WebhookDelivery.Status.FAILED, next_retry_at__lte=as_of)


class WebhookDeliveryManager(models.Manager.from_queryset(WebhookDeliveryQuerySet)):
    """``WebhookDelivery.objects`` — unfiltered, per CP7's soft-delete
    convention.
    """


class ActiveWebhookDeliveryManager(WebhookDeliveryManager):
    def get_queryset(self):
        return super().get_queryset().active()


class WebhookDelivery(SoftDeleteTimeStampedModel):
    """One attempt (and its retries) to deliver one event to one
    `WebhookEndpoint`. Written entirely by ``services.deliver_webhook()``
    — no create endpoint (see ``views.py``), the same "system writes it,
    a client only reads it" integrity boundary CP15's `CommunicationLog`/
    CP16's `ReportExecution`/CP17's `WorkflowExecution` all established.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", _("Pending")
        DELIVERED = "DELIVERED", _("Delivered")
        FAILED = "FAILED", _("Failed")

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        verbose_name=_("endpoint"),
        on_delete=models.CASCADE,
        related_name="deliveries",
    )
    event_type = models.CharField(_("event type"), max_length=100, db_index=True)
    payload = models.JSONField(_("payload"), default=dict, blank=True)
    status = models.CharField(
        _("status"), max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    response_status_code = models.PositiveSmallIntegerField(_("response status code"), null=True, blank=True)
    attempt_count = models.PositiveIntegerField(_("attempt count"), default=0)
    next_retry_at = models.DateTimeField(_("next retry at"), null=True, blank=True)
    delivered_at = models.DateTimeField(_("delivered at"), null=True, blank=True)
    error_message = models.TextField(_("error message"), blank=True, default="")

    objects = WebhookDeliveryManager()
    active_objects = ActiveWebhookDeliveryManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("webhook delivery")
        verbose_name_plural = _("webhook deliveries")
        indexes = [
            models.Index(fields=["endpoint", "status"], name="integ_delivery_status_idx"),
            models.Index(fields=["status", "next_retry_at"], name="integ_delivery_retry_idx"),
        ]

    def __str__(self):
        return f"{self.event_type} -> {self.endpoint.url} [{self.status}]"

    @property
    def owner(self):
        """Delegates TWO levels deep — through `endpoint` to
        `endpoint.integration.owner` — the same multi-level delegation
        chain CP14's `Reminder.owner` established (-> `Task`/`Event`
        .owner).
        """
        return self.endpoint.owner

    def manager_has_access(self, user):
        """Delegates to the owning ``WebhookEndpoint``'s own hook."""
        return self.endpoint.manager_has_access(user)
