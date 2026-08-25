"""CP12: reusable service functions for quoting and invoicing.

Following the CP5/CP8/CP9/CP11 pattern: narrow, single-purpose,
independently testable functions for operations with real behavior beyond
a single ORM call. `assign_owner()` is deliberately NOT redefined here —
CP9/CP10's version (``apps.crm.services.assign_owner``) already works for
anything with a plain ``owner`` FK, `Quote`/`Invoice` included, so this
module imports and reuses it directly rather than duplicating "set owner,
save" a third time. Likewise ``managed_user_ids()`` (used by
``Quote``/`Invoice.manager_has_access()`, see ``models.py``) is imported
from CP10 rather than reimplemented — see BACKEND_LEARNING_GUIDE.md CP12,
"reusing managed_user_ids() across apps", for why a cross-app import is the
right call here rather than a copy.
"""
from django.db import transaction
from django.utils import timezone

from apps.crm.services import assign_owner  # noqa: F401  (re-exported for apps.sales callers)

from .models import Invoice, InvoiceItem, PaymentTransaction, Quote, QuoteItem


# --------------------------------------------------------------------------
# Quote
# --------------------------------------------------------------------------


def create_quote(customer, quote_number, *, opportunity=None, owner=None, **extra_fields):
    """Create a ``Quote`` in ``DRAFT``. A thin wrapper — kept as a service
    function for the same single-seam reasoning as CP9's `create_lead()`.
    """
    return Quote.objects.create(
        customer=customer, quote_number=quote_number, opportunity=opportunity, owner=owner, **extra_fields
    )


def add_quote_item(quote, product_name, quantity, unit_price, *, description="", ordering=None):
    """Add a ``QuoteItem`` to ``quote`` and recalculate the quote's totals.

    ``total_price`` is always computed here (``quantity * unit_price``),
    never accepted from a caller — see ``QuoteItem.total_price``'s own
    docstring. ``ordering`` defaults to "after every existing item" when
    not supplied, so callers adding items one at a time get a sensible
    display order for free.
    """
    if ordering is None:
        last = quote.items.order_by("-ordering").first()
        ordering = (last.ordering + 1) if last else 0

    item = QuoteItem.objects.create(
        quote=quote,
        product_name=product_name,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        total_price=quantity * unit_price,
        ordering=ordering,
    )
    recalculate_quote_totals(quote)
    return item


def recalculate_quote_totals(quote):
    """Recompute ``quote.subtotal``/``total`` from its (active) line items.

    ``tax`` is left untouched — it's a value the caller sets separately
    (a flat amount or a pre-computed rate*subtotal, this model doesn't
    care which), not derived from line items the way `subtotal` is.
    Called automatically by ``add_quote_item()`` — CP12's "totals
    automatically recalculate" rule — but also exposed directly so a
    caller who edits/removes an item some other way can re-sync totals
    explicitly.
    """
    subtotal = sum((item.total_price for item in quote.items.filter(is_deleted=False)), start=type(quote.subtotal)(0))
    quote.subtotal = subtotal
    quote.total = quote.subtotal + quote.tax
    quote.save(update_fields=["subtotal", "total", "updated_at"])
    return quote


def submit_quote(quote):
    """Move a ``DRAFT`` quote to ``SUBMITTED``. Raises ``ValueError`` for
    any other starting status — a quote can only be submitted once, from
    draft.
    """
    if quote.status != Quote.Status.DRAFT:
        raise ValueError("Only a draft quote can be submitted.")
    quote.status = Quote.Status.SUBMITTED
    quote.save(update_fields=["status", "updated_at"])
    return quote


def approve_quote(quote, approved_by):
    """Approve a ``SUBMITTED`` quote — CP12's "cannot approve draft" rule
    (and, by the same check, cannot re-approve an already-approved/
    rejected/converted quote either). Stamps ``approved_by``/``approved_at``
    together.
    """
    if quote.status != Quote.Status.SUBMITTED:
        raise ValueError("Only a submitted quote can be approved.")
    quote.status = Quote.Status.APPROVED
    quote.approved_by = approved_by
    quote.approved_at = timezone.now()
    quote.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return quote


def reject_quote(quote):
    """Reject a ``SUBMITTED`` quote — CP12's "cannot reject approved" rule.
    Only a submitted quote can be rejected (a draft was never formally
    offered; an approved quote must stay approved unless a future
    checkpoint adds an explicit "revoke approval" action — not requested
    here).
    """
    if quote.status != Quote.Status.SUBMITTED:
        raise ValueError("Only a submitted quote can be rejected.")
    quote.status = Quote.Status.REJECTED
    quote.save(update_fields=["status", "updated_at"])
    return quote


@transaction.atomic
def convert_quote_to_invoice(quote, invoice_number, *, due_date=None, owner=None):
    """Convert an ``APPROVED`` quote into an ``Invoice`` — CP12's
    "conversion creates invoice / quote becomes CONVERTED / invoice starts
    SENT" rules, and "cannot convert unless approved".

    **Idempotent**: calling this a second time on an already-``CONVERTED``
    quote does NOT create a second invoice or raise — it simply returns
    the existing ``quote.converted_invoice``. This mirrors a real-world
    need (a retried request, a double-click) more usefully than raising,
    since the operation already succeeded and the caller almost always
    just wants the resulting invoice either way.

    Copies the quote's (active) line items onto the new invoice and
    recalculates the invoice's totals from them, carrying `tax` over from
    the quote unchanged (see ``recalculate_invoice_totals()``).

    ATOMICITY (Phase 4 transaction-safety audit). This is the widest
    multi-row write in the sales domain — one ``Invoice``, one
    ``InvoiceItem`` per quote line, a totals recalculation, and the
    ``Quote`` status/link update — and it is reached through a custom
    ``@action`` (``QuoteViewSet.convert``), which is NOT covered by
    ``AuditStampedModelMixin.create()``'s transaction and, with
    ``ATOMIC_REQUESTS`` off, ran with no transaction at all. A failure
    partway through left an invoice holding only some of the quote's line
    items, with totals summing only those, while the quote still read as
    ``APPROVED`` — so a retry (the documented, idempotent-looking thing to
    do) created a SECOND invoice rather than finding the first. Wrapping
    the whole sequence makes the "idempotent on an already-converted
    quote" promise in this docstring actually true: either the quote is
    converted and a complete invoice exists, or neither.
    """
    if quote.status == Quote.Status.CONVERTED and quote.converted_invoice_id is not None:
        return quote.converted_invoice

    if quote.status != Quote.Status.APPROVED:
        raise ValueError("Only an approved quote can be converted to an invoice.")

    invoice = create_invoice(
        quote.customer,
        invoice_number,
        quote=quote,
        owner=owner or quote.owner,
        due_date=due_date,
        status=Invoice.Status.SENT,
        tax=quote.tax,
    )

    for quote_item in quote.items.filter(is_deleted=False).order_by("ordering", "id"):
        InvoiceItem.objects.create(
            invoice=invoice,
            product_name=quote_item.product_name,
            description=quote_item.description,
            quantity=quote_item.quantity,
            unit_price=quote_item.unit_price,
            total_price=quote_item.total_price,
            ordering=quote_item.ordering,
        )
    recalculate_invoice_totals(invoice)

    quote.converted_invoice = invoice
    quote.status = Quote.Status.CONVERTED
    quote.save(update_fields=["converted_invoice", "status", "updated_at"])
    return invoice


# --------------------------------------------------------------------------
# Invoice
# --------------------------------------------------------------------------


def create_invoice(customer, invoice_number, *, quote=None, owner=None, **extra_fields):
    """Create an ``Invoice``. Defaults to ``DRAFT`` (the model field's own
    default) unless ``status`` is explicitly supplied — used with
    ``status=Invoice.Status.SENT`` internally by
    ``convert_quote_to_invoice()`` (CP12's "invoice starts SENT" rule for
    conversion specifically; a directly-created invoice starts as DRAFT).
    """
    return Invoice.objects.create(customer=customer, invoice_number=invoice_number, quote=quote, owner=owner, **extra_fields)


def add_invoice_item(invoice, product_name, quantity, unit_price, *, description="", ordering=None):
    """Add an ``InvoiceItem`` to ``invoice`` and recalculate its totals —
    the ``Invoice`` counterpart of ``add_quote_item()``, identical shape
    and reasoning.
    """
    if ordering is None:
        last = invoice.items.order_by("-ordering").first()
        ordering = (last.ordering + 1) if last else 0

    item = InvoiceItem.objects.create(
        invoice=invoice,
        product_name=product_name,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        total_price=quantity * unit_price,
        ordering=ordering,
    )
    recalculate_invoice_totals(invoice)
    return item


def recalculate_invoice_totals(invoice):
    """Recompute ``invoice.subtotal``/``total`` from its (active) line
    items — the ``Invoice`` counterpart of ``recalculate_quote_totals()``,
    same "tax is left untouched" reasoning.
    """
    subtotal = sum(
        (item.total_price for item in invoice.items.filter(is_deleted=False)), start=type(invoice.subtotal)(0)
    )
    invoice.subtotal = subtotal
    invoice.total = invoice.subtotal + invoice.tax
    invoice.save(update_fields=["subtotal", "total", "updated_at"])
    return invoice


def mark_invoice_paid(invoice, *, paid_at=None):
    """Mark ``invoice`` as ``PAID`` — CP12's "cancelled invoice cannot
    become paid" rule (and, by the same already-terminal check, an
    already-paid invoice cannot be marked paid a second time either,
    mirroring CP11's ``mark_won()``'s "already closed" guard).
    """
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("A cancelled invoice cannot be marked as paid.")
    if invoice.status == Invoice.Status.PAID:
        raise ValueError("This invoice is already paid.")
    invoice.status = Invoice.Status.PAID
    invoice.paid_at = paid_at or timezone.now()
    invoice.save(update_fields=["status", "paid_at", "updated_at"])
    return invoice


def cancel_invoice(invoice):
    """Cancel ``invoice`` — CP12's "paid invoice cannot be cancelled" rule
    (and, symmetrically, an already-cancelled invoice cannot be
    re-cancelled).
    """
    if invoice.status == Invoice.Status.PAID:
        raise ValueError("A paid invoice cannot be cancelled.")
    if invoice.status == Invoice.Status.CANCELLED:
        raise ValueError("This invoice is already cancelled.")
    invoice.status = Invoice.Status.CANCELLED
    invoice.save(update_fields=["status", "updated_at"])
    return invoice


def record_payment(invoice, amount, *, method=PaymentTransaction.Method.OTHER, recorded_by=None, paid_at=None, notes=""):
    """Record one payment against ``invoice`` and recalculate its status
    from the resulting total paid — the "partial payments, transaction
    history, balance" spec requirement, layered on top of (not replacing)
    ``mark_invoice_paid()``'s existing all-at-once shortcut.

    Rules, enforced here rather than left to the caller:

    - A cancelled invoice can never receive a payment.
    - ``amount`` must be strictly positive.
    - The running total paid (this payment included) can never exceed
      ``invoice.total`` — no overpayment, ever.
    - Once the running total equals ``invoice.total``, the invoice moves
      to ``PAID`` (and ``paid_at`` is set, mirroring
      ``mark_invoice_paid()``); a smaller running total moves it to
      ``PARTIAL`` instead of leaving it at ``DRAFT``/``SENT``.

    ATOMICITY AND CONCURRENCY (Phase 4 transaction-safety audit). Recording
    a payment is TWO writes that must agree — the ``PaymentTransaction``
    row and the parent invoice's recalculated ``status``/``paid_at``. Two
    separate problems were fixed here:

    1. *Partial write.* Without a transaction, a failure between the two
       writes leaves a real payment recorded against an invoice still
       showing ``SENT`` with a stale balance — a financial record and its
       ledger disagreeing. The HTTP create path happened to be covered
       already (``AuditStampedModelMixin.create()`` is atomic), but every
       non-HTTP caller — management commands, other services, future
       bulk-payment code — was not. The guarantee belongs to the operation,
       not to one of its callers.

    2. *Overpayment race.* ``remaining`` was read, checked, and then acted
       on with nothing holding the invoice still in between. Two concurrent
       payments could each independently observe the same remaining balance,
       each pass the "no overpayment, ever" check, and both commit —
       overpaying the invoice by exactly the amount the rule exists to
       prevent. The invoice row is now re-fetched under
       ``select_for_update()``, so the second request blocks until the first
       commits and then re-reads a balance that already includes it.

    Re-fetching also drops any ``_amount_paid_annotated`` value the caller's
    instance may be carrying (see ``Invoice.amount_paid``): that annotation
    is computed once when the queryset is evaluated and does NOT update when
    this function inserts a payment, so reading it back to decide the new
    status would compare against a pre-payment total and could leave a
    fully-paid invoice stuck at ``SENT``. The locked instance always
    aggregates live.
    """
    if amount is None or amount <= 0:
        raise ValueError("Payment amount must be greater than zero.")

    with transaction.atomic():
        # Locked, annotation-free view of the invoice — see the docstring.
        locked_invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)

        if locked_invoice.status == Invoice.Status.CANCELLED:
            raise ValueError("Cannot record a payment against a cancelled invoice.")

        remaining = locked_invoice.total - locked_invoice.amount_paid
        if amount > remaining:
            raise ValueError(f"Payment of {amount} exceeds the remaining balance of {remaining}.")

        payment = PaymentTransaction.objects.create(
            invoice=locked_invoice,
            amount=amount,
            method=method,
            paid_at=paid_at or timezone.now(),
            recorded_by=recorded_by,
            notes=notes,
        )

        new_total_paid = locked_invoice.amount_paid
        if new_total_paid >= locked_invoice.total:
            locked_invoice.status = Invoice.Status.PAID
            locked_invoice.paid_at = payment.paid_at
            locked_invoice.save(update_fields=["status", "paid_at", "updated_at"])
        elif new_total_paid > 0:
            locked_invoice.status = Invoice.Status.PARTIAL
            locked_invoice.save(update_fields=["status", "updated_at"])

    # Keep the caller's own instance consistent with what was just written,
    # so a view that goes on to serialize it doesn't report a stale status.
    invoice.status = locked_invoice.status
    invoice.paid_at = locked_invoice.paid_at
    return payment


__all__ = [
    "assign_owner",
    "create_quote",
    "add_quote_item",
    "recalculate_quote_totals",
    "submit_quote",
    "approve_quote",
    "reject_quote",
    "convert_quote_to_invoice",
    "create_invoice",
    "add_invoice_item",
    "recalculate_invoice_totals",
    "mark_invoice_paid",
    "cancel_invoice",
    "record_payment",
]
