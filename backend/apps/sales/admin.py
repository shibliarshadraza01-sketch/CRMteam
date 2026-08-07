"""Django admin registrations for quoting and invoicing.

Every ``ModelAdmin`` mixes in CP7's ``SoftDeleteTimeStampedAdminMixin``
(``apps.core.admin``) — unfiltered queryset, `is_deleted` in `list_filter`,
soft-delete/restore bulk actions, read-only timestamp/audit fields, all
for free, no new admin logic duplicated here.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin

from .models import Invoice, InvoiceItem, Quote, QuoteItem


class QuoteItemInline(admin.TabularInline):
    model = QuoteItem
    extra = 0
    fields = ("product_name", "quantity", "unit_price", "total_price", "ordering")
    readonly_fields = ("total_price",)
    show_change_link = True


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    fields = ("product_name", "quantity", "unit_price", "total_price", "ordering")
    readonly_fields = ("total_price",)
    show_change_link = True


@admin.register(Quote)
class QuoteAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("quote_number", "customer", "owner", "status", "total", "is_deleted")
    list_filter = ("status", "customer")
    search_fields = ("quote_number", "customer__name")
    autocomplete_fields = ("customer", "opportunity", "owner", "approved_by", "converted_invoice")
    ordering = ("-created_at",)
    inlines = [QuoteItemInline]


@admin.register(Invoice)
class InvoiceAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("invoice_number", "customer", "owner", "status", "total", "due_date", "is_deleted")
    list_filter = ("status", "customer")
    search_fields = ("invoice_number", "customer__name")
    autocomplete_fields = ("customer", "quote", "owner")
    ordering = ("-created_at",)
    inlines = [InvoiceItemInline]


@admin.register(QuoteItem)
class QuoteItemAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("product_name", "quote", "quantity", "unit_price", "total_price", "is_deleted")
    search_fields = ("product_name", "quote__quote_number")
    autocomplete_fields = ("quote",)
    ordering = ("quote", "ordering")


@admin.register(InvoiceItem)
class InvoiceItemAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("product_name", "invoice", "quantity", "unit_price", "total_price", "is_deleted")
    search_fields = ("product_name", "invoice__invoice_number")
    autocomplete_fields = ("invoice",)
    ordering = ("invoice", "ordering")
