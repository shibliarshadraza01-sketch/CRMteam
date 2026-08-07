"""CP8: tests for apps/organization/admin.py.

Django's admin site registry (``admin.site._registry``) is populated at
import time — inspecting it needs no database connection.
"""
from django.contrib import admin

from apps.core.admin import ReadOnlyTimestampsAdminMixin
from apps.organization.admin import DepartmentAdmin, MembershipAdmin, OrganizationAdmin, TeamAdmin
from apps.organization.models import Department, Membership, Organization, Team


def test_all_four_models_are_registered():
    assert Organization in admin.site._registry
    assert Department in admin.site._registry
    assert Team in admin.site._registry
    assert Membership in admin.site._registry


def test_registered_admins_are_the_expected_classes():
    assert isinstance(admin.site._registry[Organization], OrganizationAdmin)
    assert isinstance(admin.site._registry[Department], DepartmentAdmin)
    assert isinstance(admin.site._registry[Team], TeamAdmin)
    assert isinstance(admin.site._registry[Membership], MembershipAdmin)


def test_every_organization_admin_uses_readonly_timestamps_mixin():
    for admin_class in (OrganizationAdmin, DepartmentAdmin, TeamAdmin, MembershipAdmin):
        assert issubclass(admin_class, ReadOnlyTimestampsAdminMixin)


def test_organization_admin_readonly_fields_include_audit_and_timestamps():
    admin_instance = admin.site._registry[Organization]
    fields = admin_instance.get_readonly_fields(request=None)
    assert {"created_at", "updated_at", "created_by", "updated_by"} <= set(fields)


def test_organization_admin_has_department_inline():
    admin_instance = admin.site._registry[Organization]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert Department in inline_models


def test_department_admin_has_team_inline():
    admin_instance = admin.site._registry[Department]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert Team in inline_models


def test_team_admin_has_membership_inline():
    admin_instance = admin.site._registry[Team]
    inline_models = [inline.model for inline in admin_instance.inlines]
    assert Membership in inline_models


def test_admins_declare_search_fields_for_autocomplete_support():
    # autocomplete_fields on Department/Team/Membership admins reference
    # Organization/Department/Team/User admins — each of those must declare
    # search_fields or Django's system check would fail (already confirmed
    # clean via `manage.py check` during this checkpoint's verification).
    for model in (Organization, Department, Team):
        admin_instance = admin.site._registry[model]
        assert admin_instance.search_fields
