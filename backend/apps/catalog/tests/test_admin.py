"""CP13: tests for apps/catalog/admin.py. Django's admin registry is
populated at import time — no database needed.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin
from apps.catalog.admin import PriceBookAdmin, PriceBookEntryAdmin, ProductAdmin, ServiceAdmin
from apps.catalog.models import PriceBook, PriceBookEntry, Product, Service


def test_all_four_models_are_registered():
    assert Product in admin.site._registry
    assert Service in admin.site._registry
    assert PriceBook in admin.site._registry
    assert PriceBookEntry in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[Product], ProductAdmin)
    assert isinstance(admin.site._registry[Service], ServiceAdmin)
    assert isinstance(admin.site._registry[PriceBook], PriceBookAdmin)
    assert isinstance(admin.site._registry[PriceBookEntry], PriceBookEntryAdmin)


def test_every_catalog_admin_uses_soft_delete_timestamped_mixin():
    for admin_class in (ProductAdmin, ServiceAdmin, PriceBookAdmin, PriceBookEntryAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_pricebook_admin_has_entry_inline():
    admin_instance = admin.site._registry[PriceBook]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert PriceBookEntry in inline_models


def test_admins_declare_search_fields_for_autocomplete_support():
    for model in (Product, Service, PriceBook, PriceBookEntry):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
