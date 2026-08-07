"""Django admin registrations for the organization hierarchy.

Every ``ModelAdmin`` below mixes in CP7's ``ReadOnlyTimestampsAdminMixin``
(``apps.core.admin``) so ``created_at``/``updated_at``/``created_by``/
``updated_by`` are shown but never hand-edited, exactly like every other
``TimeStampedModel``-based admin is expected to from CP7 onward — no new
admin logic was written for that part.
"""
from django.contrib import admin

from apps.core.admin import ReadOnlyTimestampsAdminMixin

from .models import Department, Membership, Organization, Team


class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 0
    fields = ("name", "description")
    show_change_link = True


@admin.register(Organization)
class OrganizationAdmin(ReadOnlyTimestampsAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [DepartmentInline]


class TeamInline(admin.TabularInline):
    model = Team
    extra = 0
    fields = ("name", "manager")
    show_change_link = True


@admin.register(Department)
class DepartmentAdmin(ReadOnlyTimestampsAdminMixin, admin.ModelAdmin):
    list_display = ("name", "organization", "created_at")
    list_filter = ("organization",)
    search_fields = ("name", "organization__name")
    autocomplete_fields = ("organization",)
    inlines = [TeamInline]


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ("user", "role", "joined_at")
    autocomplete_fields = ("user",)


@admin.register(Team)
class TeamAdmin(ReadOnlyTimestampsAdminMixin, admin.ModelAdmin):
    list_display = ("name", "department", "manager", "created_at")
    list_filter = ("department__organization", "department")
    search_fields = ("name", "department__name", "manager__email")
    autocomplete_fields = ("department", "manager")
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(ReadOnlyTimestampsAdminMixin, admin.ModelAdmin):
    list_display = ("user", "team", "role", "joined_at")
    list_filter = ("role", "team__department__organization")
    search_fields = ("user__email", "team__name")
    autocomplete_fields = ("user", "team")
