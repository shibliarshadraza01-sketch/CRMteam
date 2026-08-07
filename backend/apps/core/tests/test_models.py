"""CP7: tests for the abstract base models in apps/core/models.py.

Split, following the CP4/CP5/CP6 pattern, into:

- Field/manager/class-shape checks that need NO database — these run and
  genuinely pass in this environment despite PostgreSQL being unavailable.
- Persistence round-trips (save/soft-delete/restore/hard-delete against a
  real row) that DO need a database — these use the ``core_test_tables``
  fixture (see conftest.py) and are honestly blocked here, same as every
  other ``@pytest.mark.django_db`` test since CP2.
"""
import pytest
from django.db import models

from apps.core.models import (
    ActiveManager,
    AuditModel,
    SoftDeleteManager,
    SoftDeleteModel,
    SoftDeleteQuerySet,
    SoftDeleteTimeStampedModel,
    TimeStampedModel,
)
from apps.core.tests.models import SampleRecord, SampleSoftDeleteOnly, SampleTimeStamped

# --------------------------------------------------------------------------
# No database required — field definitions, defaults, class shape
# --------------------------------------------------------------------------


def test_timestamped_model_is_abstract():
    assert TimeStampedModel._meta.abstract is True


def test_soft_delete_model_is_abstract():
    assert SoftDeleteModel._meta.abstract is True


def test_soft_delete_timestamped_model_is_abstract():
    assert SoftDeleteTimeStampedModel._meta.abstract is True


def test_audit_model_is_abstract():
    assert AuditModel._meta.abstract is True


def test_timestamped_model_has_created_and_updated_at():
    created_at = SampleTimeStamped._meta.get_field("created_at")
    updated_at = SampleTimeStamped._meta.get_field("updated_at")

    assert created_at.auto_now_add is True
    assert created_at.auto_now is False
    assert updated_at.auto_now is True
    assert updated_at.auto_now_add is False


def test_soft_delete_model_has_is_deleted_and_deleted_at():
    is_deleted = SampleSoftDeleteOnly._meta.get_field("is_deleted")
    deleted_at = SampleSoftDeleteOnly._meta.get_field("deleted_at")

    assert isinstance(is_deleted, models.BooleanField)
    assert is_deleted.default is False
    assert deleted_at.null is True
    assert deleted_at.blank is True


def test_audit_fields_present_on_every_base_model():
    for model in (SampleTimeStamped, SampleSoftDeleteOnly, SampleRecord):
        created_by = model._meta.get_field("created_by")
        updated_by = model._meta.get_field("updated_by")

        assert created_by.null is True
        assert created_by.blank is True
        assert created_by.remote_field.on_delete is models.SET_NULL
        assert updated_by.null is True
        assert updated_by.blank is True
        assert updated_by.remote_field.on_delete is models.SET_NULL


def test_audit_fields_are_not_editable_through_forms():
    # editable=False keeps created_by/updated_by out of ModelForm/admin-form
    # fields by default — they are meant to be set by code, not typed in.
    for model in (SampleTimeStamped, SampleSoftDeleteOnly, SampleRecord):
        assert model._meta.get_field("created_by").editable is False
        assert model._meta.get_field("updated_by").editable is False


def test_diamond_inheritance_produces_no_duplicate_fields():
    # SoftDeleteTimeStampedModel inherits TimeStampedModel and
    # SoftDeleteModel, both of which inherit AuditModel — verifies the
    # diamond collapses to exactly one created_by/updated_by, not two.
    field_names = [f.name for f in SampleRecord._meta.get_fields()]
    assert field_names.count("created_by") == 1
    assert field_names.count("updated_by") == 1
    assert field_names.count("created_at") == 1
    assert field_names.count("updated_at") == 1
    assert field_names.count("is_deleted") == 1
    assert field_names.count("deleted_at") == 1


def test_sample_record_has_every_expected_field():
    field_names = {f.name for f in SampleRecord._meta.get_fields()}
    assert field_names >= {
        "id", "name",
        "created_at", "updated_at",
        "created_by", "updated_by",
        "is_deleted", "deleted_at",
    }


# --------------------------------------------------------------------------
# No database required — unsaved-instance default values
# --------------------------------------------------------------------------


def test_unsaved_instance_soft_delete_defaults():
    instance = SampleRecord(name="unsaved")
    assert instance.is_deleted is False
    assert instance.deleted_at is None


def test_unsaved_instance_audit_defaults():
    instance = SampleRecord(name="unsaved")
    assert instance.created_by is None
    assert instance.updated_by is None


# --------------------------------------------------------------------------
# No database required — manager wiring
# --------------------------------------------------------------------------


def test_objects_manager_is_soft_delete_manager():
    assert isinstance(SampleRecord.objects, SoftDeleteManager)


def test_active_objects_manager_is_active_manager():
    assert isinstance(SampleRecord.active_objects, ActiveManager)


def test_active_objects_query_filters_is_deleted_false_without_hitting_db():
    # QuerySets are lazy — building one (even via a custom manager) does not
    # require a database connection, only *evaluating* one does. Inspecting
    # the compiled WHERE clause proves the filter is baked in without ever
    # touching the DB.
    queryset = SampleRecord.active_objects.all()
    where_sql = str(queryset.query.where)
    assert "is_deleted" in where_sql


def test_objects_manager_query_has_no_is_deleted_filter():
    queryset = SampleRecord.objects.all()
    assert len(queryset.query.where) == 0


def test_sample_soft_delete_only_also_gets_active_objects():
    assert isinstance(SampleSoftDeleteOnly.active_objects, ActiveManager)


def test_sample_timestamped_has_no_active_objects_manager():
    # TimeStampedModel alone (no SoftDeleteModel mixed in) has no notion of
    # "active" rows — confirms active_objects isn't accidentally leaking
    # onto models that never asked for soft delete.
    assert not hasattr(SampleTimeStamped, "active_objects")


# --------------------------------------------------------------------------
# No database required — delete() safety contract
# --------------------------------------------------------------------------


def test_soft_delete_queryset_overrides_delete():
    assert SoftDeleteQuerySet.delete is not models.QuerySet.delete


def test_soft_delete_queryset_has_a_distinctly_named_hard_delete():
    assert hasattr(SoftDeleteQuerySet, "hard_delete")
    assert SoftDeleteQuerySet.hard_delete is not SoftDeleteQuerySet.delete


def test_soft_delete_model_does_not_override_instance_level_delete():
    # Deliberate: instance.delete() must remain Django's normal hard delete
    # unless a caller explicitly opts into instance.soft_delete(). See
    # models.py's SoftDeleteModel.hard_delete() docstring for the reasoning.
    assert "delete" not in SoftDeleteModel.__dict__


def test_soft_delete_model_defines_soft_delete_and_restore_and_hard_delete():
    assert callable(SoftDeleteModel.soft_delete)
    assert callable(SoftDeleteModel.restore)
    assert callable(SoftDeleteModel.hard_delete)


# --------------------------------------------------------------------------
# Requires database — persistence round-trips
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_soft_delete_marks_row_deleted_without_removing_it(core_test_tables):
    record = SampleRecord.objects.create(name="alpha")

    record.soft_delete()

    assert record.is_deleted is True
    assert record.deleted_at is not None
    assert SampleRecord.objects.filter(pk=record.pk).exists()
    assert not SampleRecord.active_objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_restore_reverses_soft_delete(core_test_tables):
    record = SampleRecord.objects.create(name="alpha")
    record.soft_delete()

    record.restore()

    assert record.is_deleted is False
    assert record.deleted_at is None
    assert SampleRecord.active_objects.filter(pk=record.pk).exists()


@pytest.mark.django_db
def test_hard_delete_actually_removes_the_row(core_test_tables):
    record = SampleRecord.objects.create(name="alpha")
    pk = record.pk

    record.hard_delete()

    assert not SampleRecord.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_soft_delete_updates_updated_at(core_test_tables):
    record = SampleRecord.objects.create(name="alpha")
    original_updated_at = record.updated_at

    record.soft_delete()

    assert record.updated_at > original_updated_at


@pytest.mark.django_db
def test_soft_delete_stamps_updated_by_when_given(core_test_tables, django_user_model):
    user = django_user_model.objects.create_user(email="stamper@example.com", password="x")
    record = SampleRecord.objects.create(name="alpha")

    record.soft_delete(updated_by=user)

    assert record.updated_by_id == user.id


@pytest.mark.django_db
def test_active_objects_excludes_deleted_but_objects_includes_them(core_test_tables):
    visible = SampleRecord.objects.create(name="visible")
    hidden = SampleRecord.objects.create(name="hidden")
    hidden.soft_delete()

    active_names = set(SampleRecord.active_objects.values_list("name", flat=True))
    all_names = set(SampleRecord.objects.values_list("name", flat=True))

    assert active_names == {"visible"}
    assert all_names == {"visible", "hidden"}
