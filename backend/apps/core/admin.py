"""CP7: reusable Django admin mixins for soft-deletable, audited models.

Like everything else in this app, these are mixins for a future
``@admin.register`` class to combine with — there is no concrete model
registered here, since CP7 defines none.
"""
from django.contrib import admin
from django.utils.translation import gettext_lazy as _


class ReadOnlyTimestampsAdminMixin:
    """Makes ``created_at``/``updated_at``/``created_by``/``updated_by``
    visible but never editable in the admin.

    Appends to (rather than overwrites) any ``readonly_fields`` the
    concrete ``ModelAdmin`` already declares, so this can be combined with
    other admin mixins/fields without ordering-dependent surprises.
    """

    def get_readonly_fields(self, request, obj=None):
        existing = list(super().get_readonly_fields(request, obj))
        for field_name in ("created_at", "updated_at", "created_by", "updated_by"):
            if field_name not in existing and hasattr(self.model, field_name):
                existing.append(field_name)
        return existing


class SoftDeleteAdminMixin:
    """Admin support for ``SoftDeleteModel``-based models:

    - The changelist shows every row (deleted or not) — uses the model's
      default ``objects`` manager (unfiltered), consistent with
      ``apps/core/models.py``'s reasoning for why ``objects`` is
      unfiltered: an admin is exactly the place a deleted row must still be
      reachable in order to be restored.
    - ``is_deleted``/``deleted_at`` are exposed as read-only list/detail
      fields (never hand-edited — see ``SoftDeleteSerializerMixin``'s
      identical reasoning on the API side).
    - Two admin actions, ``soft_delete_selected`` and ``restore_selected``,
      replace reliance on Django's built-in "Delete selected" action (which
      performs a real hard delete) for soft-deletable models.
    """

    list_filter = ("is_deleted",)
    actions = ["soft_delete_selected", "restore_selected"]

    def get_queryset(self, request):
        # Deliberately NOT calling active_objects here — an admin must be
        # able to see and act on deleted rows (that's the whole point of
        # the restore action below); it is not the "normal" browsing view.
        return self.model.objects.all()

    def get_readonly_fields(self, request, obj=None):
        existing = list(super().get_readonly_fields(request, obj))
        for field_name in ("is_deleted", "deleted_at"):
            if field_name not in existing and hasattr(self.model, field_name):
                existing.append(field_name)
        return existing

    @admin.action(description=_("Soft-delete selected records"))
    def soft_delete_selected(self, request, queryset):
        updated = queryset.exclude(is_deleted=True).delete()
        self.message_user(request, _("Soft-deleted %(count)s record(s).") % {"count": updated})

    @admin.action(description=_("Restore selected records"))
    def restore_selected(self, request, queryset):
        restored = queryset.filter(is_deleted=True).restore()
        self.message_user(request, _("Restored %(count)s record(s).") % {"count": restored})


class SoftDeleteTimeStampedAdminMixin(SoftDeleteAdminMixin, ReadOnlyTimestampsAdminMixin):
    """Combines both admin mixins above — the base a future concrete
    ``ModelAdmin`` for a ``SoftDeleteTimeStampedModel``-based model is
    expected to actually use.
    """
