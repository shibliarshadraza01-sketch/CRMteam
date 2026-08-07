"""CP19: tests for the querysets on apps/system/models.py."""
import pytest

from apps.system.models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_auditlog_for_actor_builds_filter_without_hitting_db():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert len(AuditLog.objects.for_actor(User(pk=1)).query.where) > 0


def test_systemsetting_active_filters_is_deleted_and_is_active_without_hitting_db():
    where_sql = str(SystemSetting.objects.active().query.where)
    assert "is_deleted" in where_sql
    assert "is_active" in where_sql


def test_featureflag_active_filters_is_enabled_without_hitting_db():
    where_sql = str(FeatureFlag.objects.active().query.where)
    assert "is_enabled" in where_sql


def test_backgroundjob_by_owner_builds_filter_without_hitting_db():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert len(BackgroundJob.objects.by_owner(User(pk=1)).query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_auditlog_for_actor_matches_real_rows(employee, other_employee):
    mine = AuditLog.objects.create(actor=employee, action=AuditLog.Action.OTHER)
    AuditLog.objects.create(actor=other_employee, action=AuditLog.Action.OTHER)

    assert list(AuditLog.objects.for_actor(employee)) == [mine]


@pytest.mark.django_db
def test_active_featureflag_manager_excludes_disabled_and_deleted():
    active = FeatureFlag.objects.create(key="a", name="A", is_enabled=True)
    FeatureFlag.objects.create(key="b", name="B", is_enabled=False)
    deleted = FeatureFlag.objects.create(key="c", name="C", is_enabled=True)
    deleted.soft_delete()

    keys = set(FeatureFlag.active_objects.values_list("key", flat=True))
    assert keys == {"a"}


@pytest.mark.django_db
def test_backgroundjob_by_owner_matches_real_rows(employee, other_employee):
    mine = BackgroundJob.objects.create(name="Mine", job_type="X", owner=employee)
    BackgroundJob.objects.create(name="Theirs", job_type="X", owner=other_employee)

    assert list(BackgroundJob.objects.by_owner(employee)) == [mine]
