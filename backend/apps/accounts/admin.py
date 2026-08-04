"""Django admin configuration for the custom User model.

Built on UserAdmin rather than admin.ModelAdmin so we keep Django's
battle-tested password-change/hash-handling UI (the "change password" link,
the read-only hash display) instead of reinventing it. Field layout is
adapted for email-based login and the CRM's identity fields.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    # DjangoUserAdmin defaults assume a `username` field; every one of these
    # sections must be overridden for an email-login, username-less model.
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name")

    # add_fieldsets drives the "add user" form. It must list password1/
    # password2 (Django's own confirm-password widgets, which call
    # set_password() under the hood) rather than a raw "password" field, so a
    # plaintext password is never directly editable/stored.
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "role"),
            },
        ),
    )

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identity", {"fields": ("first_name", "last_name", "role")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    readonly_fields = ("date_joined", "updated_at", "last_login")
