"""CP9: the CRM's sales-facing domain models.

    Organization (CP8)
        \\-- Customer
                |-- ContactPerson
                \\-- Address

    Lead --(optionally converts into)--> Customer

Every model below inherits ``apps.core.models.SoftDeleteTimeStampedModel``
(CP7) — the first checkpoint to actually use the *combined* soft-delete +
timestamps base, rather than ``TimeStampedModel`` alone (CP8's choice for
its hierarchy). That's a deliberate difference from CP8: a `Customer`,
`Lead`, `ContactPerson`, or `Address` is exactly the kind of record a real
CRM needs to "delete" reversibly (a customer churns and comes back; a
contact leaves and is later reinstated) with no cascading-through-a-
hierarchy ambiguity of the kind that made CP8 avoid soft delete — see
BACKEND_LEARNING_GUIDE.md CP9, "why soft delete now, when CP8 avoided it".
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import ActiveManager, SoftDeleteManager, SoftDeleteQuerySet, SoftDeleteTimeStampedModel
from apps.organization.models import Organization


# --------------------------------------------------------------------------
# Customer
# --------------------------------------------------------------------------


class CustomerQuerySet(SoftDeleteQuerySet):
    def active(self):
        """Overrides CP7's ``SoftDeleteQuerySet.active()`` (not-deleted
        only) to ALSO require ``is_active=True`` — a `Customer` has two
        independent "is this usable" signals (soft delete, and a business
        "paused/churned" flag), and "active" for a Customer means both. See
        BACKEND_LEARNING_GUIDE.md CP9, "two independent boolean flags".
        """
        return super().active().filter(is_active=True)

    def by_owner(self, user):
        return self.filter(owner=user)

    def by_status(self, status):
        return self.filter(status=status)


class CustomerManager(models.Manager.from_queryset(CustomerQuerySet)):
    """``Customer.objects`` — unfiltered, per CP7's soft-delete manager
    convention (see ``apps.core.models.SoftDeleteManager``'s docstring).
    """


class ActiveCustomerManager(CustomerManager):
    """``Customer.active_objects`` — not-deleted AND ``is_active=True``."""

    def get_queryset(self):
        return super().get_queryset().active()


class Customer(SoftDeleteTimeStampedModel):
    class Status(models.TextChoices):
        PROSPECT = "PROSPECT", _("Prospect")
        ACTIVE = "ACTIVE", _("Active")
        INACTIVE = "INACTIVE", _("Inactive")
        CHURNED = "CHURNED", _("Churned")

    organization = models.ForeignKey(
        Organization,
        verbose_name=_("organization"),
        on_delete=models.CASCADE,
        related_name="customers",
    )
    name = models.CharField(_("name"), max_length=200)
    slug = models.SlugField(_("slug"), max_length=220)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_customers",
        help_text=_("The user (typically Manager-or-above) responsible for this account."),
    )
    status = models.CharField(
        _("status"), max_length=20, choices=Status.choices, default=Status.PROSPECT, db_index=True
    )
    industry = models.CharField(_("industry"), max_length=120, blank=True, default="")
    website = models.URLField(_("website"), blank=True, default="")
    email = models.EmailField(_("email"), blank=True, default="")
    phone = models.CharField(_("phone"), max_length=32, blank=True, default="")
    notes = models.TextField(_("notes"), blank=True, default="")
    is_active = models.BooleanField(
        _("is active"),
        default=True,
        db_index=True,
        help_text=_("Business-status flag (e.g. paused/churned), independent of soft delete."),
    )

    objects = CustomerManager()
    active_objects = ActiveCustomerManager()

    class Meta:
        ordering = ["organization", "name"]
        verbose_name = _("customer")
        verbose_name_plural = _("customers")
        constraints = [
            models.UniqueConstraint(fields=["organization", "slug"], name="crm_customer_unique_org_slug"),
        ]
        indexes = [
            models.Index(fields=["organization", "status"], name="crm_customer_org_status_idx"),
            models.Index(fields=["owner"], name="crm_customer_owner_idx"),
        ]

    def __str__(self):
        return self.name

    def manager_has_access(self, user):
        """CP10: CP6's documented per-object extension point
        (``apps.accounts.permissions.manager_has_access()``), used here so
        a Manager sees/acts on their TEAM's records, not only their own —
        "Manager has explicit access" if ``user`` manages a
        ``apps.organization`` ``Team`` this customer's ``owner`` belongs to
        (or if ``user`` IS the owner, though that path is already covered
        by ``resolve_owner()`` before this hook is even reached). See
        ``apps.crm.services.managed_user_ids()``, the single place this
        "which users does this manager see" computation lives — reused
        identically for queryset scoping (``scope_queryset_for_user()``)
        so list results and object-level permission checks never disagree.
        """
        from .services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# Lead
# --------------------------------------------------------------------------


class LeadQuerySet(SoftDeleteQuerySet):
    def by_owner(self, user):
        return self.filter(owner=user)

    def by_status(self, status):
        return self.filter(status=status)

    def converted(self):
        """Leads that have already been linked to a ``Customer``."""
        return self.filter(converted_customer__isnull=False)

    def unconverted(self):
        """Leads not yet converted — the working pipeline."""
        return self.filter(converted_customer__isnull=True)


class LeadManager(models.Manager.from_queryset(LeadQuerySet)):
    """``Lead.objects`` — unfiltered, per CP7's soft-delete convention."""


class ActiveLeadManager(LeadManager):
    """``Lead.active_objects`` — not-deleted only (CP7's plain ``active()``;
    a `Lead` has no separate business "is_active" flag the way `Customer`
    does — its lifecycle is fully expressed by ``status``).
    """

    def get_queryset(self):
        return super().get_queryset().active()


class Lead(SoftDeleteTimeStampedModel):
    class Source(models.TextChoices):
        WEBSITE = "WEBSITE", _("Website")
        REFERRAL = "REFERRAL", _("Referral")
        COLD_CALL = "COLD_CALL", _("Cold Call")
        EVENT = "EVENT", _("Event")
        ADVERTISEMENT = "ADVERTISEMENT", _("Advertisement")
        OTHER = "OTHER", _("Other")

    class Status(models.TextChoices):
        NEW = "NEW", _("New")
        CONTACTED = "CONTACTED", _("Contacted")
        QUALIFIED = "QUALIFIED", _("Qualified")
        CONVERTED = "CONVERTED", _("Converted")
        LOST = "LOST", _("Lost")

    company_name = models.CharField(_("company name"), max_length=200)
    contact_name = models.CharField(_("contact name"), max_length=200)
    email = models.EmailField(_("email"), blank=True, default="")
    phone = models.CharField(_("phone"), max_length=32, blank=True, default="")
    source = models.CharField(
        _("source"), max_length=20, choices=Source.choices, default=Source.OTHER, db_index=True
    )
    status = models.CharField(
        _("status"), max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_leads",
    )
    converted_customer = models.ForeignKey(
        Customer,
        verbose_name=_("converted customer"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="converted_from_leads",
        help_text=_("Set once this lead has been converted — see apps.crm.services.convert_lead()."),
    )
    notes = models.TextField(_("notes"), blank=True, default="")

    objects = LeadManager()
    active_objects = ActiveLeadManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("lead")
        verbose_name_plural = _("leads")
        indexes = [
            models.Index(fields=["status"], name="crm_lead_status_idx"),
            models.Index(fields=["owner"], name="crm_lead_owner_idx"),
        ]

    def __str__(self):
        return f"{self.company_name} ({self.contact_name})"

    @property
    def is_converted(self):
        return self.converted_customer_id is not None

    def manager_has_access(self, user):
        """See ``Customer.manager_has_access()`` — identical reasoning,
        applied to a `Lead`'s own ``owner``.
        """
        from .services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


# --------------------------------------------------------------------------
# ContactPerson
# --------------------------------------------------------------------------


class ContactPerson(SoftDeleteTimeStampedModel):
    customer = models.ForeignKey(
        Customer,
        verbose_name=_("customer"),
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    first_name = models.CharField(_("first name"), max_length=150)
    last_name = models.CharField(_("last name"), max_length=150)
    designation = models.CharField(_("designation"), max_length=150, blank=True, default="")
    email = models.EmailField(_("email"), blank=True, default="")
    phone = models.CharField(_("phone"), max_length=32, blank=True, default="")
    is_primary = models.BooleanField(_("is primary contact"), default=False)

    objects = SoftDeleteManager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["customer", "-is_primary", "last_name", "first_name"]
        verbose_name = _("contact person")
        verbose_name_plural = _("contact persons")
        constraints = [
            # At most one primary contact per customer, enforced at the
            # database level via a partial (conditional) unique index —
            # see BACKEND_LEARNING_GUIDE.md CP9, "enforcing a business rule
            # with a partial unique constraint".
            models.UniqueConstraint(
                fields=["customer"],
                condition=models.Q(is_primary=True),
                name="crm_contactperson_unique_primary_per_customer",
            ),
        ]
        indexes = [
            models.Index(fields=["customer"], name="crm_contactperson_customer_idx"),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def owner(self):
        """Lets ``apps.core.permissions.IsOwnerOrSuperAdmin`` resolve this
        contact's owning ``Customer``'s owner as ITS owner too — a contact
        has no owner of its own, but "who may act on this contact" should
        follow the same account manager who owns the customer it belongs
        to. See ``resolve_owner()`` (CP6/CP7) and CP8's ``Team.owner``/
        ``Membership.owner`` for the precedent this follows.
        """
        return self.customer.owner

    def manager_has_access(self, user):
        """Delegates to the owning ``Customer``'s own hook — see
        ``Customer.manager_has_access()``.
        """
        return self.customer.manager_has_access(user)


# --------------------------------------------------------------------------
# Address
# --------------------------------------------------------------------------


class Address(SoftDeleteTimeStampedModel):
    class AddressType(models.TextChoices):
        BILLING = "BILLING", _("Billing")
        SHIPPING = "SHIPPING", _("Shipping")

    customer = models.ForeignKey(
        Customer,
        verbose_name=_("customer"),
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(
        _("address type"), max_length=20, choices=AddressType.choices, db_index=True
    )
    line1 = models.CharField(_("address line 1"), max_length=255)
    line2 = models.CharField(_("address line 2"), max_length=255, blank=True, default="")
    city = models.CharField(_("city"), max_length=120)
    state = models.CharField(_("state"), max_length=120, blank=True, default="")
    country = models.CharField(_("country"), max_length=120)
    postal_code = models.CharField(_("postal code"), max_length=20, blank=True, default="")

    objects = SoftDeleteManager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["customer", "address_type"]
        verbose_name = _("address")
        verbose_name_plural = _("addresses")
        indexes = [
            models.Index(fields=["customer", "address_type"], name="crm_address_customer_type_idx"),
        ]

    def __str__(self):
        return f"{self.get_address_type_display()} — {self.line1}, {self.city}"

    @property
    def owner(self):
        """See ``ContactPerson.owner`` — same reasoning, same precedent."""
        return self.customer.owner

    def manager_has_access(self, user):
        """Delegates to the owning ``Customer``'s own hook — see
        ``Customer.manager_has_access()``.
        """
        return self.customer.manager_has_access(user)


# --------------------------------------------------------------------------
# CP11: Opportunity (sales pipeline) — defined in opportunities.py, kept in
# its own module (see that file's docstring for why), but re-exported here
# so Django's app-loading machinery — which only auto-imports THIS module,
# apps/crm/models.py, as the app's models — actually discovers them. An
# import with no local use is unusual, but this one is load-bearing: without
# it, `Opportunity`/`OpportunityActivity`/`OpportunityNote` would silently
# never be registered with the app registry at all (confirmed empirically —
# `apps.get_model("crm", "Opportunity")` raises `LookupError` without this
# import), not merely "not exported from this module".
# --------------------------------------------------------------------------
from .opportunities import Opportunity, OpportunityActivity, OpportunityNote  # noqa: E402,F401
