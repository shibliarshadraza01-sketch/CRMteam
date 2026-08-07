"""CP19: tests for apps/system/filters.py."""
import pytest

from apps.system.filters import BackgroundJobFilterSet, FeatureFlagFilterSet
from apps.system.models import BackgroundJob, FeatureFlag

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_backgroundjob_filterset_declares_expected_fields():
    assert set(BackgroundJobFilterSet.Meta.fields) == {"job_type", "status", "owner"}


def test_featureflag_filterset_declares_expected_fields():
    assert set(FeatureFlagFilterSet.Meta.fields) == {"is_enabled"}


def test_status_filter_builds_query_without_hitting_db():
    filterset = BackgroundJobFilterSet(data={"status": "PENDING"}, queryset=BackgroundJob.objects.all())
    assert filterset.is_valid()
    assert len(filterset.qs.query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_status_filter_matches_real_rows(employee):
    pending = BackgroundJob.objects.create(name="A", job_type="X", owner=employee)
    BackgroundJob.objects.create(name="B", job_type="X", owner=employee, status=BackgroundJob.Status.COMPLETED)

    filterset = BackgroundJobFilterSet(data={"status": "PENDING"}, queryset=BackgroundJob.objects.all())

    assert list(filterset.qs) == [pending]


@pytest.mark.django_db
def test_is_enabled_filter_matches_real_rows():
    enabled = FeatureFlag.objects.create(key="a", name="A", is_enabled=True)
    FeatureFlag.objects.create(key="b", name="B", is_enabled=False)

    filterset = FeatureFlagFilterSet(data={"is_enabled": "true"}, queryset=FeatureFlag.objects.all())

    assert list(filterset.qs) == [enabled]
