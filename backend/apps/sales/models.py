"""CP12: quoting and invoicing.

    Customer (CP9)
        |-- Opportunity (CP11, optional link)
        \\-- Quote --(approved, then converted)--> Invoice
                |-- QuoteItem            |-- InvoiceItem

Every model inherits ``apps.core.models.SoftDeleteTimeStampedModel`` (CP7),
exactly like every CP9+ CRM record — a quote or invoice is exactly the
kind of business document that should be reversibly "deleted" (voided,
then restored if that was a mistake), not permanently erased.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import ActiveManager, SoftDeleteManager, SoftDeleteQuerySet, SoftDeleteTimeStampedModel
from apps.crm.models import Customer
from apps.crm.opportunities import Opportunity


# --------------------------------------------------------------------------
# Quote
# --------------------------------------------------------------------------


class QuoteQuerySet(SoftDeleteQuerySet):
    def draft(self):
        return self.filter(status=Quote.Status.DRAFT)

    def submitted(self):
        return self.filter(status=Quote.Status.SUBMITTED)

    def approved(self):
        return self.filter(status=Quote.Status.APPROVED)

    def rejected(self):
        return self.filter(status=Quote.Status.REJECTED)

    def converted(self):
        return self.filter(status=Quote.Status.CONVERTED)


class QuoteManager(models.Manager.from_queryset(QuoteQuerySet)):
    """``Quote.objects`` — unfiltered, per CP7's soft-delete convention."""


class ActiveQuoteManager(QuoteManager):
    """``Quote.active_objects`` — not-deleted only."""

    def get_queryset(self):
        return super().get_queryset().active()


class Quote(SoftDeleteTimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Draft")
        SUBMITTED = "SUBMITTED", _("Submitted")
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")
        CONVERTED = "CONVERTED", _("Converted")

    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"), on_delete=models.CASCADE, related_name="quotes"
    )
    opportunity = models.ForeignKey(
        Opportunity,
        verbose_name=_("opportunity"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quotes",
        help_text=_("The deal this quote was drafted for, if any."),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_quotes",
    )
    quote_number = models.CharField(_("quote number"), max_length=50, unique=True)
    status = models.CharField(
        _("status"), max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    valid_until = models.DateField(_("valid until"), null=True, blank=True)
    subtotal = models.DecimalField(_("subtotal"), max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(_("tax"), max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(_("total"), max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(_("notes"), blank=True, default="")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("approved by"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_quotes",
    )
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)
    converted_invoice = models.ForeignKey(
        "sales.Invoice",
        verbose_name=_("converted invoice"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_quote",
        help_text=_("Set once this quote has been converted — see apps.sales.services.convert_quote_to_invoice()."),
    )

    objects = QuoteManager()
    active_objects = ActiveQuoteManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("quote")
        verbose_name_plural = _("quotes")
        indexes = [
            models.Index(fields=["customer", "status"], name="sales_quote_cust_status_idx"),
            models.Index(fields=["owner"], name="sales_quote_owner_idx"),
            models.Index(fields=["valid_until"], name="sales_quote_valid_until_idx"),
        ]

    def __str__(self):
        return self.quote_number

    def manager_has_access(self, user):
        """See CP11's ``Opportunity.manager_has_access()`` — identical
        reasoning, reusing CP10's ``managed_user_ids()`` directly (imported
        from ``apps.crm.services``, not duplicated here — see
        BACKEND_LEARNING_GUIDE.md CP12, "reusing managed_user_ids() across
        apps").
        """
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


class QuoteItem(SoftDeleteTimeStampedModel):
    quote = models.ForeignKey(Quote, verbose_name=_("quote"), on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField(_("product name"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")
    quantity = models.DecimalField(_("quantity"), max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(_("unit price"), max_digits=12, decimal_places=2, default=0)
    total_price = models.DecimalField(
        _("total price"), max_digits=14, decimal_places=2, default=0,
        help_text=_("quantity * unit_price — recalculated by apps.sales.services, never hand-edited."),
    )
    ordering = models.PositiveIntegerField(_("ordering"), default=0)

    objects = SoftDeleteManager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["quote", "ordering", "id"]
        verbose_name = _("quote item")
        verbose_name_plural = _("quote items")
        indexes = [
            models.Index(fields=["quote", "ordering"], name="sales_quoteitem_order_idx"),
        ]

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    @property
    def owner(self):
        """See CP9's ``ContactPerson.owner``/``Address.owner`` — same
        "belongs to an owned parent" delegation.
        """
        return self.quote.owner

    def manager_has_access(self, user):
        return self.quote.manager_has_access(user)


# --------------------------------------------------------------------------
# Invoice
# --------------------------------------------------------------------------


class InvoiceQuerySet(SoftDeleteQuerySet):
    def draft(self):
        return self.filter(status=Invoice.Status.DRAFT)

    def sent(self):
        return self.filter(status=Invoice.Status.SENT)

    def paid(self):
        return self.filter(status=Invoice.Status.PAID)

    def cancelled(self):
        return self.filter(status=Invoice.Status.CANCELLED)

    def overdue(self, today=None):
        """Invoices past their ``due_date`` that are neither paid nor
        cancelled — the standard "needs a follow-up" collections view.
        ``today`` is injectable for testing, same reasoning as CP11's
        ``Opportunity.objects.expected_this_month()``.
        """
        from django.utils import timezone

        today = today or timezone.now().date()
        return self.filter(due_date__lt=today).exclude(
            status__in=[Invoice.Status.PAID, Invoice.Status.CANCELLED]
        )


class InvoiceManager(models.Manager.from_queryset(InvoiceQuerySet)):
    """``Invoice.objects`` — unfiltered, per CP7's soft-delete convention."""


class ActiveInvoiceManager(InvoiceManager):
    """``Invoice.active_objects`` — not-deleted only."""

    def get_queryset(self):
        return super().get_queryset().active()


class Invoice(SoftDeleteTimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", _("Draft")
        SENT = "SENT", _("Sent")
        PAID = "PAID", _("Paid")
        CANCELLED = "CANCELLED", _("Cancelled")

    customer = models.ForeignKey(
        Customer, verbose_name=_("customer"), on_delete=models.CASCADE, related_name="invoices"
    )
    quote = models.ForeignKey(
        Quote,
        verbose_name=_("quote"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
        help_text=_("The quote this invoice was converted from, if any."),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("owner"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_invoices",
    )
    invoice_number = models.CharField(_("invoice number"), max_length=50, unique=True)
    status = models.CharField(
        _("status"), max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    due_date = models.DateField(_("due date"), null=True, blank=True)
    subtotal = models.DecimalField(_("subtotal"), max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(_("tax"), max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(_("total"), max_digits=14, decimal_places=2, default=0)
    paid_at = models.DateTimeField(_("paid at"), null=True, blank=True)

    objects = InvoiceManager()
    active_objects = ActiveInvoiceManager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")
        indexes = [
            models.Index(fields=["customer", "status"], name="sales_invoice_cust_status_idx"),
            models.Index(fields=["owner"], name="sales_invoice_owner_idx"),
            models.Index(fields=["due_date"], name="sales_invoice_due_date_idx"),
        ]

    def __str__(self):
        return self.invoice_number

    def manager_has_access(self, user):
        """See ``Quote.manager_has_access()`` — identical reasoning."""
        from apps.crm.services import managed_user_ids

        return self.owner_id is not None and self.owner_id in managed_user_ids(user)


class InvoiceItem(SoftDeleteTimeStampedModel):
    invoice = models.ForeignKey(Invoice, verbose_name=_("invoice"), on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField(_("product name"), max_length=200)
    description = models.TextField(_("description"), blank=True, default="")
    quantity = models.DecimalField(_("quantity"), max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(_("unit price"), max_digits=12, decimal_places=2, default=0)
    total_price = models.DecimalField(
        _("total price"), max_digits=14, decimal_places=2, default=0,
        help_text=_("quantity * unit_price — recalculated by apps.sales.services, never hand-edited."),
    )
    ordering = models.PositiveIntegerField(_("ordering"), default=0)

    objects = SoftDeleteManager()
    active_objects = ActiveManager()

    class Meta:
        ordering = ["invoice", "ordering", "id"]
        verbose_name = _("invoice item")
        verbose_name_plural = _("invoice items")
        indexes = [
            models.Index(fields=["invoice", "ordering"], name="sales_invoiceitem_order_idx"),
        ]

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    @property
    def owner(self):
        return self.invoice.owner

    def manager_has_access(self, user):
        return self.invoice.manager_has_access(user)
