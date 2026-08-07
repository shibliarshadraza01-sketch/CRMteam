"""CP12: tests for apps/sales/admin.py. Django's admin registry is
populated at import time — no database needed.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin
from apps.sales.admin import InvoiceAdmin, InvoiceItemAdmin, QuoteAdmin, QuoteItemAdmin
from apps.sales.models import Invoice, InvoiceItem, Quote, QuoteItem


def test_all_four_models_are_registered():
    assert Quote in admin.site._registry
    assert QuoteItem in admin.site._registry
    assert Invoice in admin.site._registry
    assert InvoiceItem in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[Quote], QuoteAdmin)
    assert isinstance(admin.site._registry[QuoteItem], QuoteItemAdmin)
    assert isinstance(admin.site._registry[Invoice], InvoiceAdmin)
    assert isinstance(admin.site._registry[InvoiceItem], InvoiceItemAdmin)


def test_every_sales_admin_uses_soft_delete_timestamped_mixin():
    for admin_class in (QuoteAdmin, QuoteItemAdmin, InvoiceAdmin, InvoiceItemAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_quote_admin_has_item_inline():
    admin_instance = admin.site._registry[Quote]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert QuoteItem in inline_models


def test_invoice_admin_has_item_inline():
    admin_instance = admin.site._registry[Invoice]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert InvoiceItem in inline_models


def test_admins_declare_search_fields_for_autocomplete_support():
    for model in (Quote, QuoteItem, Invoice, InvoiceItem):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
