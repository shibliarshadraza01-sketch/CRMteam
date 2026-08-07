"""CP7: tests for apps/core/serializers.py.

Every mixin here is a plain ``serializers.Serializer`` subclass — DRF
serializer field declarations are inspected via ``.fields`` without ever
needing a request, a view, or a database, so this entire file needs no DB
connection.
"""
from rest_framework import serializers

from apps.core.serializers import (
    AuditSerializerMixin,
    SoftDeleteSerializerMixin,
    SoftDeleteTimeStampedSerializerMixin,
    TimeStampedSerializerMixin,
)


def test_timestamped_mixin_declares_read_only_timestamp_fields():
    fields = TimeStampedSerializerMixin().fields

    assert isinstance(fields["created_at"], serializers.DateTimeField)
    assert isinstance(fields["updated_at"], serializers.DateTimeField)
    assert fields["created_at"].read_only is True
    assert fields["updated_at"].read_only is True


def test_audit_mixin_declares_read_only_pk_fields():
    fields = AuditSerializerMixin().fields

    assert isinstance(fields["created_by"], serializers.PrimaryKeyRelatedField)
    assert isinstance(fields["updated_by"], serializers.PrimaryKeyRelatedField)
    assert fields["created_by"].read_only is True
    assert fields["updated_by"].read_only is True


def test_soft_delete_mixin_declares_read_only_fields():
    fields = SoftDeleteSerializerMixin().fields

    assert isinstance(fields["is_deleted"], serializers.BooleanField)
    assert fields["is_deleted"].read_only is True
    assert fields["deleted_at"].read_only is True
    assert fields["deleted_at"].allow_null is True


def test_combined_mixin_has_every_field_from_all_three():
    fields = SoftDeleteTimeStampedSerializerMixin().fields

    expected = {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"}
    assert expected <= set(fields.keys())


def test_combined_mixin_all_fields_are_read_only():
    fields = SoftDeleteTimeStampedSerializerMixin().fields

    for name in ("created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"):
        assert fields[name].read_only is True, f"{name} should be read-only"


def test_mixins_reject_client_supplied_values_on_validation():
    # A read-only field is simply excluded from validated_data — supplying
    # one in input data must not raise, and must not appear in the result,
    # proving a client truly cannot set these through normal input.
    serializer = SoftDeleteTimeStampedSerializerMixin(
        data={"is_deleted": True, "created_by": 999, "created_at": "2020-01-01T00:00:00Z"}
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {}
