"""CP12: the sales domain's REST API (quoting and invoicing).

Reuses CP10's ``_CrmModelViewSet`` (``apps.crm.views``) directly rather
than redefining the identical base (HTTP-method restriction, CP6's
``IsOwnerOrSuperAdmin``, the active-vs-unfiltered ``get_queryset()``
split) a second time — that class has no CRM-specific logic in its own
implementation, only its current location; importing it is a deliberate
"reuse over duplicate" choice per CP12's own instructions, not an
architectural layering violation (`apps.sales` already depends on
`apps.crm` for `Customer`/`Opportunity`). A future checkpoint could
promote it to `apps.core.views` if a THIRD app ever needs the same base —
not done here since only two apps use it today and CP12 didn't ask for
that refactor.
"""
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.permissions import assert_object_accessible
from apps.core.utils import stamp_audit_fields
from apps.crm.services import resolve_owner_for_create
from apps.crm.views import _CrmModelViewSet

from .filters import InvoiceFilterSet, PaymentTransactionFilterSet, QuoteFilterSet
from .models import Invoice, InvoiceItem, PaymentTransaction, Quote, QuoteItem
from .serializers import (
    InvoiceDetailSerializer,
    InvoiceItemSerializer,
    InvoiceSerializer,
    PaymentTransactionSerializer,
    QuoteDetailSerializer,
    QuoteItemSerializer,
    QuoteSerializer,
)
from .services import (
    add_invoice_item,
    add_quote_item,
    approve_quote,
    assign_owner,
    cancel_invoice,
    convert_quote_to_invoice,
    create_invoice,
    create_quote,
    mark_invoice_paid,
    record_payment,
    reject_quote,
    submit_quote,
)


class QuoteViewSet(_CrmModelViewSet):
    """CRUD (list/create/retrieve/patch/delete, no PUT — via
    ``_CrmModelViewSet``) plus four stage-transition actions
    (``submit``, ``approve``, ``reject``, ``convert``), each a thin
    wrapper around the matching ``apps/sales/services.py`` function so the
    actual business rules live in exactly one place. No action here
    declares its own ``permission_classes`` override — every one is
    reached via ``self.get_object()``, which runs the same
    ``IsOwnerOrSuperAdmin`` object-level check as ordinary retrieve/
    update/destroy.
    """

    base_manager = Quote.objects
    base_active_manager = Quote.active_objects
    serializer_class = QuoteSerializer
    filterset_class = QuoteFilterSet
    search_fields = ["quote_number", "customer__name"]
    ordering_fields = ["created_at", "valid_until", "total", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("customer", "owner", "opportunity", "approved_by")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return QuoteDetailSerializer
        return QuoteSerializer

    def perform_create(self, serializer):
        """Routes creation through ``create_quote()`` and defaults
        ``owner`` to the requesting user when not explicitly supplied —
        the same rule ``CustomerViewSet``/``LeadViewSet``/
        ``OpportunityViewSet`` already apply (CP10/CP11).
        """
        data = dict(serializer.validated_data)
        customer = data.pop("customer")
        assert_object_accessible(self.request, customer)
        quote_number = data.pop("quote_number")
        owner = data.pop("owner", None)

        quote = create_quote(customer, quote_number, **data)
        assign_owner(quote, resolve_owner_for_create(self.request.user, owner))
        stamp_audit_fields(quote, self.request.user, creating=True)
        quote.save()
        serializer.instance = quote

    def _quote_response(self, quote):
        serializer = self.get_serializer(quote)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: QuoteSerializer})
    @action(detail=True, methods=["post"])
    def submit(self, request, *args, **kwargs):
        """``POST /quotes/<id>/submit/`` — DRAFT -> SUBMITTED
        (``services.submit_quote()``).
        """
        quote = self.get_object()
        try:
            submit_quote(quote)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._quote_response(quote)

    @extend_schema(request=None, responses={200: QuoteSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, *args, **kwargs):
        """``POST /quotes/<id>/approve/`` — SUBMITTED -> APPROVED
        (``services.approve_quote()``); "cannot approve draft".
        """
        quote = self.get_object()
        try:
            approve_quote(quote, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._quote_response(quote)

    @extend_schema(request=None, responses={200: QuoteSerializer})
    @action(detail=True, methods=["post"])
    def reject(self, request, *args, **kwargs):
        """``POST /quotes/<id>/reject/`` — SUBMITTED -> REJECTED
        (``services.reject_quote()``); "cannot reject approved".
        """
        quote = self.get_object()
        try:
            reject_quote(quote)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._quote_response(quote)

    @extend_schema(request=None, responses={200: InvoiceSerializer})
    @action(detail=True, methods=["post"])
    def convert(self, request, *args, **kwargs):
        """``POST /quotes/<id>/convert/`` — APPROVED -> CONVERTED, creating
        an ``Invoice`` (``services.convert_quote_to_invoice()``);
        idempotent — calling this again on an already-converted quote
        returns the same invoice rather than erroring.
        """
        quote = self.get_object()
        invoice_number = request.data.get("invoice_number")
        if not invoice_number:
            return Response(
                {"detail": "invoice_number is required."}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            invoice = convert_quote_to_invoice(quote, invoice_number)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = InvoiceSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)


class QuoteItemViewSet(_CrmModelViewSet):
    base_manager = QuoteItem.objects
    base_active_manager = QuoteItem.active_objects
    serializer_class = QuoteItemSerializer
    owner_field = "quote__owner"
    ordering = ["quote", "ordering"]

    def get_queryset(self):
        return super().get_queryset().select_related("quote", "quote__owner")

    def perform_create(self, serializer):
        """Routes creation through ``add_quote_item()`` — real behavior:
        auto-assigns ``ordering`` when omitted and recalculates the
        parent quote's totals (CP12's "totals automatically recalculate"
        rule).
        """
        data = dict(serializer.validated_data)
        quote = data.pop("quote")
        assert_object_accessible(self.request, quote)
        product_name = data.pop("product_name")
        quantity = data.pop("quantity")
        unit_price = data.pop("unit_price")
        data.pop("total_price", None)  # always computed, never accepted

        item = add_quote_item(quote, product_name, quantity, unit_price, **data)
        stamp_audit_fields(item, self.request.user, creating=True)
        item.save()
        serializer.instance = item


class InvoiceViewSet(_CrmModelViewSet):
    """CRUD plus two payment-lifecycle actions (``mark-paid``, ``cancel``),
    each a thin wrapper around ``apps/sales/services.py``.
    """

    base_manager = Invoice.objects
    base_active_manager = Invoice.active_objects
    serializer_class = InvoiceSerializer
    filterset_class = InvoiceFilterSet
    search_fields = ["invoice_number", "customer__name"]
    ordering_fields = ["created_at", "due_date", "total", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Annotates `amount_paid` in the same query (one LEFT JOIN + SUM,
        # filtered to non-deleted payments) instead of letting
        # Invoice.amount_paid's property run a separate aggregate query
        # per row — the difference between one query and N+1 queries for
        # a page of invoices. See Invoice.amount_paid's own docstring for
        # the matching property-side fallback (a directly-fetched
        # instance, e.g. in services.py, still computes it correctly,
        # just via a query instead of an annotation).
        return (
            super()
            .get_queryset()
            .select_related("customer", "owner", "quote")
            .annotate(
                _amount_paid_annotated=Coalesce(
                    Sum("payments__amount", filter=Q(payments__is_deleted=False)),
                    Value(0),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return InvoiceDetailSerializer
        return InvoiceSerializer

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        customer = data.pop("customer")
        assert_object_accessible(self.request, customer)
        invoice_number = data.pop("invoice_number")
        owner = data.pop("owner", None)

        invoice = create_invoice(customer, invoice_number, **data)
        assign_owner(invoice, resolve_owner_for_create(self.request.user, owner))
        stamp_audit_fields(invoice, self.request.user, creating=True)
        invoice.save()
        serializer.instance = invoice

    def _invoice_response(self, invoice):
        serializer = self.get_serializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: InvoiceSerializer})
    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, *args, **kwargs):
        """``POST /invoices/<id>/mark-paid/`` — "cancelled invoice cannot
        become paid" (``services.mark_invoice_paid()``).
        """
        invoice = self.get_object()
        try:
            mark_invoice_paid(invoice)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._invoice_response(invoice)

    @extend_schema(request=None, responses={200: InvoiceSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, *args, **kwargs):
        """``POST /invoices/<id>/cancel/`` — "paid invoice cannot be
        cancelled" (``services.cancel_invoice()``).
        """
        invoice = self.get_object()
        try:
            cancel_invoice(invoice)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._invoice_response(invoice)


class InvoiceItemViewSet(_CrmModelViewSet):
    base_manager = InvoiceItem.objects
    base_active_manager = InvoiceItem.active_objects
    serializer_class = InvoiceItemSerializer
    owner_field = "invoice__owner"
    ordering = ["invoice", "ordering"]

    def get_queryset(self):
        return super().get_queryset().select_related("invoice", "invoice__owner")

    def perform_create(self, serializer):
        """Routes creation through ``services.add_invoice_item()`` — same
        auto-ordering + totals-recalculation behavior as
        ``QuoteItemViewSet``.
        """
        data = dict(serializer.validated_data)
        invoice = data.pop("invoice")
        assert_object_accessible(self.request, invoice)
        product_name = data.pop("product_name")
        quantity = data.pop("quantity")
        unit_price = data.pop("unit_price")
        data.pop("total_price", None)

        item = add_invoice_item(invoice, product_name, quantity, unit_price, **data)
        stamp_audit_fields(item, self.request.user, creating=True)
        item.save()
        serializer.instance = item


class PaymentTransactionViewSet(_CrmModelViewSet):
    """Create/list/retrieve only — no PATCH and no soft-delete via plain
    DELETE (a recorded payment is a financial record; correcting one
    means recording an offsetting entry, not silently rewriting history).
    ``hard-delete`` remains reachable for Managers/Super Admins via
    CP7's mixin, same as every other CP10+ model — this narrowing only
    removes the ordinary edit/soft-delete surface, not the existing
    role-gated administrative override.
    """

    http_method_names = ["get", "post", "head", "options"]
    base_manager = PaymentTransaction.objects
    base_active_manager = PaymentTransaction.active_objects
    serializer_class = PaymentTransactionSerializer
    filterset_class = PaymentTransactionFilterSet
    owner_field = "invoice__owner"
    ordering_fields = ["paid_at", "amount"]
    ordering = ["-paid_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("invoice", "invoice__owner", "recorded_by")

    def get_throttles(self):
        # Rate-limited: recording a payment is a real, data-mutating
        # financial operation — see config/settings/base.py's
        # "expensive_operation" scope docstring. list/retrieve on this
        # viewset are unaffected.
        if self.action == "create":
            self.throttle_scope = "expensive_operation"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def perform_create(self, serializer):
        """Routes creation through ``services.record_payment()`` — real
        behavior: rejects overpayment and payments against a cancelled
        invoice, and recalculates the parent invoice's status
        (``PARTIAL``/``PAID``) as a side effect.
        """
        data = dict(serializer.validated_data)
        invoice = data.pop("invoice")
        assert_object_accessible(self.request, invoice)
        amount = data.pop("amount")

        try:
            transaction = record_payment(invoice, amount, recorded_by=self.request.user, **data)
        except ValueError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc

        stamp_audit_fields(transaction, self.request.user, creating=True)
        transaction.save()
        serializer.instance = transaction
