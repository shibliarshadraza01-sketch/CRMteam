"""CP9: tests for apps/crm/admin.py.

Django's admin site registry is populated at import time — inspecting it
needs no database connection.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin
from apps.crm.admin import AddressAdmin, ContactPersonAdmin, CustomerAdmin, LeadAdmin
from apps.crm.models import Address, ContactPerson, Customer, Lead


def test_all_four_models_are_registered():
    assert Customer in admin.site._registry
    assert Lead in admin.site._registry
    assert ContactPerson in admin.site._registry
    assert Address in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[Customer], CustomerAdmin)
    assert isinstance(admin.site._registry[Lead], LeadAdmin)
    assert isinstance(admin.site._registry[ContactPerson], ContactPersonAdmin)
    assert isinstance(admin.site._registry[Address], AddressAdmin)


def test_every_crm_admin_uses_soft_delete_timestamped_mixin():
    for admin_class in (CustomerAdmin, LeadAdmin, ContactPersonAdmin, AddressAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_customer_admin_has_contact_and_address_inlines():
    admin_instance = admin.site._registry[Customer]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert ContactPerson in inline_models
    assert Address in inline_models


def test_customer_admin_readonly_fields_include_soft_delete_and_audit():
    admin_instance = admin.site._registry[Customer]
    fields = set(admin_instance.get_readonly_fields(request=None))
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= fields


def test_customer_admin_get_queryset_is_unfiltered():
    admin_instance = admin.site._registry[Customer]
    queryset = admin_instance.get_queryset(request=None)
    assert len(queryset.query.where) == 0


def test_customer_admin_declares_soft_delete_actions():
    admin_instance = admin.site._registry[Customer]
    assert "soft_delete_selected" in admin_instance.actions
    assert "restore_selected" in admin_instance.actions


def test_lead_admin_list_filter_includes_status_and_source():
    admin_instance = admin.site._registry[Lead]
    assert "status" in admin_instance.list_filter
    assert "source" in admin_instance.list_filter


def test_admins_declare_search_fields_for_autocomplete_support():
    for model in (Customer, Lead, ContactPerson, Address):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
