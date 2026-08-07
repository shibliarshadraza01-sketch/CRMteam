"""CP11: tests for the Opportunity-related admin registrations. Django's
admin registry is populated at import time — no database needed.
"""
from django.contrib import admin

from apps.core.admin import SoftDeleteTimeStampedAdminMixin
from apps.crm.admin import OpportunityActivityAdmin, OpportunityAdmin, OpportunityNoteAdmin
from apps.crm.opportunities import Opportunity, OpportunityActivity, OpportunityNote


def test_all_three_models_are_registered():
    assert Opportunity in admin.site._registry
    assert OpportunityActivity in admin.site._registry
    assert OpportunityNote in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[Opportunity], OpportunityAdmin)
    assert isinstance(admin.site._registry[OpportunityActivity], OpportunityActivityAdmin)
    assert isinstance(admin.site._registry[OpportunityNote], OpportunityNoteAdmin)


def test_every_opportunity_admin_uses_soft_delete_timestamped_mixin():
    for admin_class in (OpportunityAdmin, OpportunityActivityAdmin, OpportunityNoteAdmin):
        assert issubclass(admin_class, SoftDeleteTimeStampedAdminMixin)


def test_opportunity_admin_has_note_and_activity_inlines():
    admin_instance = admin.site._registry[Opportunity]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert OpportunityNote in inline_models
    assert OpportunityActivity in inline_models


def test_opportunity_admin_list_filter_includes_stage_and_closed_won():
    admin_instance = admin.site._registry[Opportunity]
    assert "stage" in admin_instance.list_filter
    assert "is_closed" in admin_instance.list_filter
    assert "is_won" in admin_instance.list_filter


def test_admins_declare_search_fields_for_autocomplete_support():
    for model in (Opportunity, OpportunityActivity, OpportunityNote):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
