"""Django admin registrations for the catalog domain.

Every ``ModelAdmin`` mixes in CP7's ``SoftDeleteTimeStampedAdminMixin`` —
unfiltered queryset, `is_deleted` in `list_filter`, soft-delete/restore
bulk actions, read-only timestamp/audit fields, all for free.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin

from .models import PriceBook, PriceBookEntry, Product, Service


@admin.register(Product)
class ProductAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "sku", "default_price", "currency", "is_active", "is_deleted")
    list_filter = ("is_active", "currency")
    search_fields = ("name", "sku")
    ordering = ("name",)


@admin.register(Service)
class ServiceAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "code", "default_rate", "currency", "is_active", "is_deleted")
    list_filter = ("is_active", "currency")
    search_fields = ("name", "code")
    ordering = ("name",)


class PriceBookEntryInline(admin.TabularInline):
    model = PriceBookEntry
    extra = 0
    fields = ("product", "service", "price", "is_active")
    autocomplete_fields = ("product", "service")
    show_change_link = True


@admin.register(PriceBook)
class PriceBookAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "currency", "is_active", "is_deleted")
    list_filter = ("is_active", "currency")
    search_fields = ("name",)
    ordering = ("name",)
    inlines = [PriceBookEntryInline]


@admin.register(PriceBookEntry)
class PriceBookEntryAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("price_book", "product", "service", "price", "is_active", "is_deleted")
    list_filter = ("is_active", "price_book")
    search_fields = ("price_book__name", "product__name", "product__sku", "service__name", "service__code")
    autocomplete_fields = ("price_book", "product", "service")
    ordering = ("price_book", "product", "service")
