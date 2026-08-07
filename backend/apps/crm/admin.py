"""Django admin registrations for the CRM domain.

Every ``ModelAdmin`` below mixes in CP7's ``SoftDeleteTimeStampedAdminMixin``
(``apps.core.admin``) — unfiltered queryset (deleted rows stay visible/
restorable), `is_deleted` in `list_filter`, soft-delete/restore bulk
actions, and read-only timestamp/audit fields — all for free, no new admin
logic duplicated here.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin

from .models import Address, ContactPerson, Customer, Lead
from .opportunities import Opportunity, OpportunityActivity, OpportunityNote


class ContactPersonInline(admin.TabularInline):
    model = ContactPerson
    extra = 0
    fields = ("first_name", "last_name", "designation", "email", "phone", "is_primary")
    show_change_link = True


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ("address_type", "line1", "city", "country", "postal_code")
    show_change_link = True


@admin.register(Customer)
class CustomerAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("name", "organization", "owner", "status", "is_active", "is_deleted")
    list_filter = ("status", "industry", "is_active", "organization")
    search_fields = ("name", "slug", "email", "phone")
    autocomplete_fields = ("organization", "owner")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("organization", "name")
    inlines = [ContactPersonInline, AddressInline]


@admin.register(Lead)
class LeadAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("company_name", "contact_name", "status", "source", "owner", "converted_customer")
    list_filter = ("status", "source")
    search_fields = ("company_name", "contact_name", "email", "phone")
    autocomplete_fields = ("owner", "converted_customer")
    ordering = ("-created_at",)


@admin.register(ContactPerson)
class ContactPersonAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("full_name", "customer", "designation", "is_primary", "is_deleted")
    list_filter = ("is_primary",)
    search_fields = ("first_name", "last_name", "email", "customer__name")
    autocomplete_fields = ("customer",)
    ordering = ("customer", "-is_primary", "last_name")


@admin.register(Address)
class AddressAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("customer", "address_type", "city", "country", "is_deleted")
    list_filter = ("address_type", "country")
    search_fields = ("line1", "city", "postal_code", "customer__name")
    autocomplete_fields = ("customer",)
    ordering = ("customer", "address_type")


class OpportunityNoteInline(admin.TabularInline):
    model = OpportunityNote
    extra = 0
    fields = ("content",)
    show_change_link = True


class OpportunityActivityInline(admin.TabularInline):
    model = OpportunityActivity
    extra = 0
    fields = ("activity_type", "subject", "occurred_at")
    show_change_link = True


@admin.register(Opportunity)
class OpportunityAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("title", "customer", "owner", "stage", "value", "is_closed", "is_won", "is_deleted")
    list_filter = ("stage", "is_closed", "is_won", "currency")
    search_fields = ("title", "customer__name", "description")
    autocomplete_fields = ("customer", "owner")
    ordering = ("-created_at",)
    inlines = [OpportunityNoteInline, OpportunityActivityInline]


@admin.register(OpportunityActivity)
class OpportunityActivityAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("subject", "opportunity", "activity_type", "occurred_at", "is_deleted")
    list_filter = ("activity_type",)
    search_fields = ("subject", "notes", "opportunity__title")
    autocomplete_fields = ("opportunity",)
    ordering = ("-occurred_at",)


@admin.register(OpportunityNote)
class OpportunityNoteAdmin(SoftDeleteTimeStampedAdminMixin, admin.ModelAdmin):
    list_display = ("opportunity", "created_at", "created_by", "is_deleted")
    search_fields = ("content", "opportunity__title")
    autocomplete_fields = ("opportunity",)
    ordering = ("-created_at",)
