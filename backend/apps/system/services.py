"""CP19: reusable service functions for the system/platform domain.

Ownership scoping is NOT reimplemented — CP10's `managed_user_ids()`/
`scope_queryset_for_user()` are imported directly from `apps.crm.services`,
the same reuse every checkpoint since CP12 has applied.
"""
import hashlib

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.crm.services import managed_user_ids, scope_queryset_for_user  # noqa: F401 (re-exported)

from .models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting

# --------------------------------------------------------------------------
# Audit logging
# --------------------------------------------------------------------------


def log_audit_event(actor, action, *, related_object=None, changes=None, description="", ip_address=None):
    """Create one `AuditLog` entry. The single place every audit entry in
    this project is ever created — called automatically by
    `signals.py`'s `post_save` receivers, and available directly for any
    service that wants to log something signals don't cover (e.g. a
    LOGIN event, which has no associated model save).
    """
    extra_fields = {}
    if related_object is not None:
        extra_fields["content_type"] = ContentType.objects.get_for_model(related_object)
        extra_fields["object_id"] = related_object.pk

    return AuditLog.objects.create(
        actor=actor, action=action, description=description, changes=changes or {}, ip_address=ip_address,
        **extra_fields,
    )


# --------------------------------------------------------------------------
# Settings management
# --------------------------------------------------------------------------


def get_setting(key, default=None):
    """Return an active `SystemSetting`'s `value`, or `default` if the key
    doesn't exist (or is inactive/soft-deleted). Never raises
    `SystemSetting.DoesNotExist` — a missing setting is an expected,
    normal outcome for a caller to handle via `default`, not an error.
    """
    setting = SystemSetting.active_objects.filter(key=key).first()
    return setting.value if setting is not None else default


def set_setting(key, value, *, description=""):
    """Create or update the `SystemSetting` for `key`. A thin
    create-or-update wrapper — kept as a service function so a future
    validation rule (e.g. "some keys have a fixed value shape") has one
    seam, the same reasoning as CP9's `add_address()`.
    """
    setting, _created = SystemSetting.objects.update_or_create(
        key=key, defaults={"value": value, "description": description, "is_active": True}
    )
    return setting


# --------------------------------------------------------------------------
# Feature-flag evaluation
# --------------------------------------------------------------------------


def is_feature_enabled(flag_key, *, user=None):
    """Evaluate whether `flag_key` is enabled — for `user` specifically,
    if `rollout_percentage` is less than 100.

    Returns `False` for an unknown, inactive, or master-disabled flag
    (fail closed — an unrecognized flag is never silently "on"). When
    `rollout_percentage == 100`, every user sees the same answer.
    Otherwise, a user's inclusion is DETERMINISTIC — the same
    `(flag_key, user_id)` pair always evaluates the same way (via a
    stable hash of the two, taken modulo 100), so a user doesn't flicker
    between enabled/disabled across requests, but different users are
    spread roughly evenly across the rollout percentage. `user=None`
    with `rollout_percentage < 100` always returns `False` — a
    percentage rollout is meaningless without a stable per-user identity
    to hash.
    """
    flag = FeatureFlag.active_objects.filter(key=flag_key).first()
    if flag is None or not flag.is_enabled:
        return False
    if flag.rollout_percentage >= 100:
        return True
    if flag.rollout_percentage <= 0:
        return False
    if user is None:
        return False

    digest = hashlib.sha256(f"{flag_key}:{user.pk}".encode("utf-8")).hexdigest()
    bucket = int(digest, 16) % 100
    return bucket < flag.rollout_percentage


# --------------------------------------------------------------------------
# Background job tracking
# --------------------------------------------------------------------------


def create_background_job(name, job_type, *, owner=None):
    """Create a PENDING `BackgroundJob`. A thin wrapper — kept as a
    service function for the same single-seam reasoning as CP9's
    `create_lead()`.
    """
    return BackgroundJob.objects.create(name=name, job_type=job_type, owner=owner)


def start_background_job(job):
    """Transition `job` to RUNNING. Raises `ValueError` if it isn't
    currently PENDING — the same "already closed"-shaped guard as CP11's
    `mark_won()`, applied to the OTHER end of a lifecycle (can't start
    what's already running/finished).
    """
    if job.status != BackgroundJob.Status.PENDING:
        raise ValueError(f"Cannot start a job that is already {job.status}.")

    job.status = BackgroundJob.Status.RUNNING
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at", "updated_at"])
    return job


def complete_background_job(job, *, result_data=None):
    """Transition `job` to COMPLETED. Raises `ValueError` if it isn't
    currently RUNNING.
    """
    if job.status != BackgroundJob.Status.RUNNING:
        raise ValueError(f"Cannot complete a job that is not running (status={job.status}).")

    job.status = BackgroundJob.Status.COMPLETED
    job.result_data = result_data or {}
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "result_data", "completed_at", "updated_at"])
    return job


def fail_background_job(job, error_message):
    """Transition `job` to FAILED. Raises `ValueError` if it isn't
    currently RUNNING. Unlike `complete_background_job()`, failure is
    allowed to happen mid-flight without a prior "attempt" concept — the
    same shape as `deliver_webhook()`'s own single-attempt failure
    recording (CP18).
    """
    if job.status != BackgroundJob.Status.RUNNING:
        raise ValueError(f"Cannot fail a job that is not running (status={job.status}).")

    job.status = BackgroundJob.Status.FAILED
    job.error_message = error_message
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "error_message", "completed_at", "updated_at"])
    return job


__all__ = [
    "managed_user_ids",
    "scope_queryset_for_user",
    "log_audit_event",
    "get_setting",
    "set_setting",
    "is_feature_enabled",
    "create_background_job",
    "start_background_job",
    "complete_background_job",
    "fail_background_job",
]
