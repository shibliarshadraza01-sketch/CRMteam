"""CP7: tests for SoftDeleteQuerySet/SoftDeleteManager/ActiveManager bulk
(queryset-level) behavior — distinct from test_models.py's instance-level
soft_delete()/restore()/hard_delete() coverage.
"""
import pytest

from apps.core.tests.models import SampleRecord

# --------------------------------------------------------------------------
# No database required — queryset method presence/naming contract
# --------------------------------------------------------------------------


def test_queryset_exposes_active_and_deleted_filters():
    queryset = SampleRecord.objects.all()
    assert hasattr(queryset, "active")
    assert hasattr(queryset, "deleted")


def test_queryset_delete_and_hard_delete_are_distinct_callables():
    queryset = SampleRecord.objects.all()
    assert queryset.delete is not queryset.hard_delete


def test_active_manager_queryset_still_has_full_queryset_api():
    # ActiveManager pre-filters but must not lose the rest of
    # SoftDeleteQuerySet's API (deleted(), hard_delete(), restore()).
    queryset = SampleRecord.active_objects.all()
    assert hasattr(queryset, "deleted")
    assert hasattr(queryset, "hard_delete")
    assert hasattr(queryset, "restore")


# --------------------------------------------------------------------------
# Requires database — bulk operations actually affecting rows
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_bulk_delete_on_queryset_is_soft_not_hard(core_test_tables):
    SampleRecord.objects.create(name="a")
    SampleRecord.objects.create(name="b")

    affected = SampleRecord.objects.all().delete()

    assert affected == 2
    # Still present in the table (unfiltered manager), just marked deleted.
    assert SampleRecord.objects.count() == 2
    assert SampleRecord.objects.filter(is_deleted=True).count() == 2


@pytest.mark.django_db
def test_bulk_hard_delete_actually_removes_rows(core_test_tables):
    SampleRecord.objects.create(name="a")
    SampleRecord.objects.create(name="b")

    SampleRecord.objects.all().hard_delete()

    assert SampleRecord.objects.count() == 0


@pytest.mark.django_db
def test_bulk_restore_on_queryset(core_test_tables):
    SampleRecord.objects.create(name="a")
    SampleRecord.objects.create(name="b")
    SampleRecord.objects.all().delete()

    restored = SampleRecord.objects.filter(is_deleted=True).restore()

    assert restored == 2
    assert SampleRecord.active_objects.count() == 2


@pytest.mark.django_db
def test_deleted_helper_returns_only_deleted_rows(core_test_tables):
    keep = SampleRecord.objects.create(name="keep")
    gone = SampleRecord.objects.create(name="gone")
    gone.soft_delete()

    deleted_names = set(SampleRecord.objects.deleted().values_list("name", flat=True))

    assert deleted_names == {"gone"}


@pytest.mark.django_db
def test_active_helper_matches_active_objects_manager(core_test_tables):
    SampleRecord.objects.create(name="visible")
    hidden = SampleRecord.objects.create(name="hidden")
    hidden.soft_delete()

    via_helper = set(SampleRecord.objects.active().values_list("name", flat=True))
    via_manager = set(SampleRecord.active_objects.values_list("name", flat=True))

    assert via_helper == via_manager == {"visible"}
