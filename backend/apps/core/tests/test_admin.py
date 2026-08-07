"""CP7: tests for apps/core/admin.py.

The admin mixins are exercised against lightweight stand-ins for a real
``ModelAdmin`` (a plain base providing ``get_readonly_fields``/``model``,
mirroring how Django's own ``admin.ModelAdmin`` supplies them) rather than
a full Django admin site — enough to prove the mixin logic itself, without
needing an actual registered admin or a request/response cycle.
"""
import pytest

from apps.core.admin import (
    ReadOnlyTimestampsAdminMixin,
    SoftDeleteAdminMixin,
    SoftDeleteTimeStampedAdminMixin,
)
from apps.core.tests.models import SampleRecord

# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class _FakeBaseAdmin:
    model = SampleRecord

    def get_readonly_fields(self, request, obj=None):
        return []

    def message_user(self, request, message):
        self.messages = getattr(self, "messages", [])
        self.messages.append(message)


class ReadOnlyTimestampsAdmin(ReadOnlyTimestampsAdminMixin, _FakeBaseAdmin):
    pass


class SoftDeleteAdmin(SoftDeleteAdminMixin, _FakeBaseAdmin):
    pass


class CombinedAdmin(SoftDeleteTimeStampedAdminMixin, _FakeBaseAdmin):
    pass


# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_readonly_timestamps_mixin_appends_timestamp_and_audit_fields():
    admin_instance = ReadOnlyTimestampsAdmin()

    fields = admin_instance.get_readonly_fields(request=None)

    assert set(fields) == {"created_at", "updated_at", "created_by", "updated_by"}


def test_readonly_timestamps_mixin_does_not_duplicate_existing_fields():
    class AlreadyHasCreatedAt(_FakeBaseAdmin):
        def get_readonly_fields(self, request, obj=None):
            return ["created_at"]

    class Combined(ReadOnlyTimestampsAdminMixin, AlreadyHasCreatedAt):
        pass

    fields = Combined().get_readonly_fields(request=None)

    assert fields.count("created_at") == 1


def test_soft_delete_admin_mixin_readonly_includes_soft_delete_fields():
    admin_instance = SoftDeleteAdmin()

    fields = admin_instance.get_readonly_fields(request=None)

    assert set(fields) == {"is_deleted", "deleted_at"}


def test_soft_delete_admin_mixin_list_filter_includes_is_deleted():
    assert "is_deleted" in SoftDeleteAdminMixin.list_filter


def test_soft_delete_admin_mixin_declares_both_actions():
    assert "soft_delete_selected" in SoftDeleteAdminMixin.actions
    assert "restore_selected" in SoftDeleteAdminMixin.actions


def test_soft_delete_admin_mixin_get_queryset_uses_unfiltered_manager():
    admin_instance = SoftDeleteAdmin()

    queryset = admin_instance.get_queryset(request=None)

    # Unfiltered — same contract as the model's own `objects` manager (an
    # admin must be able to see and restore deleted rows).
    assert len(queryset.query.where) == 0


def test_combined_admin_mixin_has_readonly_fields_from_both():
    admin_instance = CombinedAdmin()

    fields = admin_instance.get_readonly_fields(request=None)

    assert set(fields) == {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"}


# --------------------------------------------------------------------------
# Requires database — the actions actually mutate rows
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_soft_delete_selected_action_soft_deletes_the_queryset(core_test_tables):
    SampleRecord.objects.create(name="a")
    SampleRecord.objects.create(name="b")
    admin_instance = SoftDeleteAdmin()

    admin_instance.soft_delete_selected(request=None, queryset=SampleRecord.objects.all())

    assert SampleRecord.active_objects.count() == 0
    assert SampleRecord.objects.filter(is_deleted=True).count() == 2


@pytest.mark.django_db
def test_restore_selected_action_restores_the_queryset(core_test_tables):
    SampleRecord.objects.create(name="a")
    SampleRecord.objects.all().delete()
    admin_instance = SoftDeleteAdmin()

    admin_instance.restore_selected(request=None, queryset=SampleRecord.objects.all())

    assert SampleRecord.active_objects.count() == 1
