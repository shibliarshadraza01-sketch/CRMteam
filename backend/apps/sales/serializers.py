"""CP12: serializers for quoting and invoicing.

Every serializer mixes in CP7's ``SoftDeleteTimeStampedSerializerMixin``
(``apps.core.serializers``), exactly like every CP9+ CRM serializer. Per
CP12's spec ("Nested detail serializers only"), each writable serializer
exposes its foreign keys as plain primary keys with NO nested
representations at all — nesting (line items, the owner's safe user info,
the customer's name) is reserved entirely for the ``*DetailSerializer``
variants, used only on ``retrieve`` (see ``views.py``), following CP9/
CP10/CP11's identical writable/detail split.

``status`` (on both `Quote` and `Invoice`) and the workflow-only fields
(`Quote`'s `approved_by`/`approved_at`/`converted_invoice`; both models'
computed `subtotal`/`total`) are read-only on EVERY serializer, including
the writable ones — CP12 provides a dedicated action for every state
transition (`submit`/`approve`/`reject`/`convert`, `mark-paid`/`cancel`),
so there is no supported way to reach a new `status` through a plain
`PATCH`, unlike CP11's `Opportunity.stage` (which still allowed free
movement between its non-terminal states via `PATCH`).

Class order below is deliberate: ``QuoteSerializer`` first (no
dependencies), then ``InvoiceSerializer`` (no dependencies), then
``QuoteDetailSerializer`` (nests ``InvoiceSerializer`` for
``converted_invoice``), then ``InvoiceDetailSerializer`` (nests
``QuoteSerializer`` for ``quote``) — this ordering avoids any circular
class-definition problem entirely; neither detail serializer needs the
OTHER model's detail variant (nesting `InvoiceDetailSerializer` inside
`QuoteDetailSerializer`, and vice versa, would actually be circular and is
deliberately avoided the same way CP9's `LeadDetailSerializer` avoided
nesting a full `CustomerDetailSerializer`).
"""
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.core.serializers import SoftDeleteTimeStampedSerializerMixin

from .models import Invoice, InvoiceItem, Quote, QuoteItem


class _SalesSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base: every sales serializer gets the CP7 timestamp/audit/
    soft-delete field shape without repeating it per class.
    """


# --------------------------------------------------------------------------
# QuoteItem / InvoiceItem
# --------------------------------------------------------------------------


class QuoteItemSerializer(_SalesSerializer):
    total_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = QuoteItem
        fields = [
            "id", "quote", "product_name", "description", "quantity", "unit_price", "total_price", "ordering",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class InvoiceItemSerializer(_SalesSerializer):
    total_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = InvoiceItem
        fields = [
            "id", "invoice", "product_name", "description", "quantity", "unit_price", "total_price", "ordering",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


# --------------------------------------------------------------------------
# Quote (writable)
# --------------------------------------------------------------------------


class QuoteSerializer(_SalesSerializer):
    status = serializers.ChoiceField(choices=Quote.Status.choices, read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    approved_by = serializers.PrimaryKeyRelatedField(read_only=True)
    approved_at = serializers.DateTimeField(read_only=True)
    converted_invoice = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Quote
        fields = [
            "id", "customer", "opportunity", "owner", "quote_number", "status", "valid_until",
            "subtotal", "tax", "total", "notes", "approved_by", "approved_at", "converted_invoice",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


# --------------------------------------------------------------------------
# Invoice (writable)
# --------------------------------------------------------------------------


class InvoiceSerializer(_SalesSerializer):
    status = serializers.ChoiceField(choices=Invoice.Status.choices, read_only=True)
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    paid_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "customer", "quote", "owner", "invoice_number", "status", "due_date",
            "subtotal", "tax", "total", "paid_at",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


# --------------------------------------------------------------------------
# Quote (detail — read-only, nested)
# --------------------------------------------------------------------------


class QuoteDetailSerializer(QuoteSerializer):
    """Read-only: nests the owner's/approver's safe user info, the
    customer's name, this quote's line items, and — once converted — the
    resulting invoice (as a plain, non-detail ``InvoiceSerializer``,
    avoiding the same unbounded nesting depth CP9's ``LeadDetailSerializer``
    already avoided by nesting ``CustomerSerializer`` rather than
    ``CustomerDetailSerializer`` for its own converted-record link).
    """

    owner = UserSerializer(read_only=True)
    approved_by = UserSerializer(read_only=True)
    converted_invoice = InvoiceSerializer(read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    items = QuoteItemSerializer(many=True, read_only=True)

    class Meta(QuoteSerializer.Meta):
        fields = QuoteSerializer.Meta.fields + ["customer_name", "items"]
        read_only_fields = fields


# --------------------------------------------------------------------------
# Invoice (detail — read-only, nested)
# --------------------------------------------------------------------------


class InvoiceDetailSerializer(InvoiceSerializer):
    """Read-only: nests the owner's safe user info, the customer's name,
    this invoice's line items, and (if converted from one) the source
    quote as a plain ``QuoteSerializer``.
    """

    owner = UserSerializer(read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    quote = QuoteSerializer(read_only=True)
    items = InvoiceItemSerializer(many=True, read_only=True)

    class Meta(InvoiceSerializer.Meta):
        fields = InvoiceSerializer.Meta.fields + ["customer_name", "items"]
        read_only_fields = fields
