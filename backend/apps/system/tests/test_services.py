"""CP19: tests for apps/system/services.py."""
import pytest

from apps.system.models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting
from apps.system.services import (
    complete_background_job,
    create_background_job,
    fail_background_job,
    get_setting,
    is_feature_enabled,
    log_audit_event,
    managed_user_ids,
    scope_queryset_for_user,
    set_setting,
    start_background_job,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_managed_user_ids_and_scope_queryset_for_user_are_reexported_from_crm():
    from apps.crm import services as crm_services

    assert managed_user_ids is crm_services.managed_user_ids
    assert scope_queryset_for_user is crm_services.scope_queryset_for_user


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_log_audit_event_creates_entry(employee, customer):
    log = log_audit_event(employee, AuditLog.Action.OTHER, related_object=customer, description="Manual note")
    assert log.actor == employee
    assert log.description == "Manual note"
    assert log.related_object == customer


@pytest.mark.django_db
def test_get_setting_returns_default_when_missing():
    assert get_setting("does_not_exist", "fallback") == "fallback"


@pytest.mark.django_db
def test_set_setting_then_get_setting_round_trips():
    set_setting("max_items", 42, description="Max items per page")
    assert get_setting("max_items") == 42


@pytest.mark.django_db
def test_set_setting_updates_existing_key():
    set_setting("k", "first")
    set_setting("k", "second")

    assert get_setting("k") == "second"
    assert SystemSetting.objects.filter(key="k").count() == 1


@pytest.mark.django_db
def test_get_setting_ignores_inactive_setting():
    setting = SystemSetting.objects.create(key="retired", value="x", is_active=False)
    assert get_setting("retired", "fallback") == "fallback"


@pytest.mark.django_db
def test_is_feature_enabled_false_for_unknown_flag(employee):
    assert is_feature_enabled("does_not_exist", user=employee) is False


@pytest.mark.django_db
def test_is_feature_enabled_false_when_master_switch_off(employee):
    FeatureFlag.objects.create(key="f", name="F", is_enabled=False, rollout_percentage=100)
    assert is_feature_enabled("f", user=employee) is False


@pytest.mark.django_db
def test_is_feature_enabled_true_at_full_rollout(employee):
    FeatureFlag.objects.create(key="f", name="F", is_enabled=True, rollout_percentage=100)
    assert is_feature_enabled("f", user=employee) is True


@pytest.mark.django_db
def test_is_feature_enabled_false_at_zero_rollout(employee):
    FeatureFlag.objects.create(key="f", name="F", is_enabled=True, rollout_percentage=0)
    assert is_feature_enabled("f", user=employee) is False


@pytest.mark.django_db
def test_is_feature_enabled_false_without_user_at_partial_rollout():
    FeatureFlag.objects.create(key="f", name="F", is_enabled=True, rollout_percentage=50)
    assert is_feature_enabled("f", user=None) is False


@pytest.mark.django_db
def test_is_feature_enabled_is_deterministic_per_user(employee):
    FeatureFlag.objects.create(key="f", name="F", is_enabled=True, rollout_percentage=50)

    first = is_feature_enabled("f", user=employee)
    second = is_feature_enabled("f", user=employee)

    assert first == second


@pytest.mark.django_db
def test_create_background_job_defaults_to_pending(employee):
    job = create_background_job("Export", "EXPORT", owner=employee)
    assert job.status == BackgroundJob.Status.PENDING


@pytest.mark.django_db
def test_start_background_job_transitions_to_running(job):
    start_background_job(job)
    job.refresh_from_db()
    assert job.status == BackgroundJob.Status.RUNNING
    assert job.started_at is not None


@pytest.mark.django_db
def test_start_background_job_rejects_non_pending(job):
    start_background_job(job)
    with pytest.raises(ValueError):
        start_background_job(job)


@pytest.mark.django_db
def test_complete_background_job_transitions_to_completed(job):
    start_background_job(job)
    complete_background_job(job, result_data={"rows": 10})
    job.refresh_from_db()
    assert job.status == BackgroundJob.Status.COMPLETED
    assert job.result_data == {"rows": 10}
    assert job.completed_at is not None


@pytest.mark.django_db
def test_complete_background_job_rejects_non_running(job):
    with pytest.raises(ValueError):
        complete_background_job(job)


@pytest.mark.django_db
def test_fail_background_job_transitions_to_failed(job):
    start_background_job(job)
    fail_background_job(job, "connection lost")
    job.refresh_from_db()
    assert job.status == BackgroundJob.Status.FAILED
    assert job.error_message == "connection lost"


@pytest.mark.django_db
def test_fail_background_job_rejects_non_running(job):
    with pytest.raises(ValueError):
        fail_background_job(job, "x")
