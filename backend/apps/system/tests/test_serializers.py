"""CP19: tests for apps/system/serializers.py."""
import pytest
from rest_framework import serializers

from apps.system.serializers import (
    AuditLogSerializer,
    BackgroundJobSerializer,
    FeatureFlagSerializer,
    SystemSettingSerializer,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_auditlog_serializer_is_entirely_read_only():
    for name, field in AuditLogSerializer().fields.items():
        assert field.read_only is True


def test_auditlog_serializer_has_no_soft_delete_fields():
    fields = AuditLogSerializer().fields
    assert "is_deleted" not in fields
    assert "deleted_at" not in fields


def test_systemsetting_serializer_fields():
    fields = SystemSettingSerializer().fields
    assert {
        "id", "key", "value", "description", "is_active",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_featureflag_serializer_rejects_out_of_range_rollout():
    serializer = FeatureFlagSerializer()
    with pytest.raises(serializers.ValidationError):
        serializer.validate_rollout_percentage(150)


def test_featureflag_serializer_accepts_valid_rollout():
    serializer = FeatureFlagSerializer()
    assert serializer.validate_rollout_percentage(50) == 50


def test_backgroundjob_serializer_status_fields_are_read_only():
    fields = BackgroundJobSerializer().fields
    for name in ("status", "started_at", "completed_at", "result_data", "error_message"):
        assert fields[name].read_only is True


def test_backgroundjob_serializer_name_and_job_type_are_writable():
    fields = BackgroundJobSerializer().fields
    assert fields["name"].read_only is False
    assert fields["job_type"].read_only is False


# --------------------------------------------------------------------------
# Requires database — full serializer validation (FK fields query the DB)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_systemsetting_serializer_full_validation():
    serializer = SystemSettingSerializer(data={"key": "x", "value": 1})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_backgroundjob_serializer_full_validation(employee):
    serializer = BackgroundJobSerializer(data={"name": "Export", "job_type": "EXPORT", "owner": employee.pk})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_auditlog_serializer_output_includes_related_object(customer):
    from apps.system.services import log_audit_event

    log = log_audit_event(None, "OTHER", related_object=customer, description="x")
    data = AuditLogSerializer(log).data

    assert data["related_object"]["label"] == str(customer)
