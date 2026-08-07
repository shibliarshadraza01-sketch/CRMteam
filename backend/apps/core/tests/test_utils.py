"""CP7: tests for apps/core/utils.py."""
import pytest
from django.contrib.auth import get_user_model

from apps.core.tests.models import SampleRecord, SampleTimeStamped
from apps.core.utils import (
    active_queryset,
    bulk_restore,
    bulk_soft_delete,
    is_soft_deletable,
    restore,
    soft_delete,
    stamp_audit_fields,
    touch,
)

User = get_user_model()


def _unsaved_user():
    return User(email="stamper@example.com", role=User.Role.EMPLOYEE)


# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_stamp_audit_fields_sets_created_by_when_creating():
    instance = SampleRecord(name="x")
    user = _unsaved_user()

    stamp_audit_fields(instance, user, creating=True)

    assert instance.created_by is user
    assert instance.updated_by is user


def test_stamp_audit_fields_does_not_touch_created_by_when_updating():
    instance = SampleRecord(name="x")
    original_creator = _unsaved_user()
    instance.created_by = original_creator
    updater = _unsaved_user()

    stamp_audit_fields(instance, updater, creating=False)

    assert instance.created_by is original_creator
    assert instance.updated_by is updater


def test_stamp_audit_fields_no_op_when_user_is_none():
    instance = SampleRecord(name="x")

    result = stamp_audit_fields(instance, None, creating=True)

    assert result is instance
    assert instance.created_by is None
    assert instance.updated_by is None


def test_is_soft_deletable_true_for_soft_delete_model():
    assert is_soft_deletable(SampleRecord) is True


def test_is_soft_deletable_false_for_plain_timestamped_model():
    assert is_soft_deletable(SampleTimeStamped) is False


def test_active_queryset_uses_active_objects_when_available():
    queryset = active_queryset(SampleRecord)
    where_sql = str(queryset.query.where)
    assert "is_deleted" in where_sql


def test_active_queryset_falls_back_to_objects_for_non_soft_deletable_model():
    queryset = active_queryset(SampleTimeStamped)
    assert len(queryset.query.where) == 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_soft_delete_util_wraps_instance_method(core_test_tables):
    record = SampleRecord.objects.create(name="alpha")

    result = soft_delete(record)

    assert result is record
    assert record.is_deleted is True


@pytest.mark.django_db
def test_restore_util_wraps_instance_method(core_test_tables):
    record = SampleRecord.objects.create(name="alpha")
    record.soft_delete()

    result = restore(record)

    assert result is record
    assert record.is_deleted is False


@pytest.mark.django_db
def test_bulk_soft_delete_util(core_test_tables):
    SampleRecord.objects.create(name="a")
    SampleRecord.objects.create(name="b")

    affected = bulk_soft_delete(SampleRecord.objects.all())

    assert affected == 2
    assert SampleRecord.active_objects.count() == 0


@pytest.mark.django_db
def test_bulk_restore_util(core_test_tables):
    SampleRecord.objects.create(name="a")
    SampleRecord.objects.all().delete()

    restored = bulk_restore(SampleRecord.objects.filter(is_deleted=True))

    assert restored == 1
    assert SampleRecord.active_objects.count() == 1


@pytest.mark.django_db
def test_bulk_soft_delete_stamps_updated_by(core_test_tables, django_user_model):
    user = django_user_model.objects.create_user(email="bulk@example.com", password="x")
    SampleRecord.objects.create(name="a")
    SampleRecord.objects.create(name="b")

    bulk_soft_delete(SampleRecord.objects.all(), updated_by=user)

    assert all(
        record.updated_by_id == user.id for record in SampleRecord.objects.all()
    )


@pytest.mark.django_db
def test_touch_advances_updated_at_without_changing_other_fields(core_test_tables):
    record = SampleRecord.objects.create(name="alpha")
    original_updated_at = record.updated_at

    touch(record)

    assert record.updated_at > original_updated_at
    assert record.name == "alpha"
