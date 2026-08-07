"""CP15: tests for apps/communications/serializers.py."""
import pytest
from rest_framework import serializers

from apps.communications.serializers import (
    CommunicationLogSerializer,
    EmailMessageQueueSerializer,
    EmailMessageSerializer,
    EmailTemplateSerializer,
    NotificationSerializer,
)

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_email_template_serializer_fields():
    fields = EmailTemplateSerializer().fields
    assert {
        "id", "name", "subject", "body", "is_active",
        "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
    } == set(fields.keys())


def test_email_message_serializer_fields_include_related_object():
    fields = EmailMessageSerializer().fields
    assert "related_object" in fields
    assert fields["related_object"].read_only is True


def test_email_message_serializer_output_fields_are_read_only():
    fields = EmailMessageSerializer().fields
    for name in ("subject", "body", "status", "sent_at", "error_message"):
        assert fields[name].read_only is True


def test_notification_serializer_is_read_and_read_at_are_read_only():
    fields = NotificationSerializer().fields
    assert fields["is_read"].read_only is True
    assert fields["read_at"].read_only is True


def test_communication_log_serializer_is_entirely_read_only():
    for name, field in CommunicationLogSerializer().fields.items():
        assert field.read_only is True


def test_queue_serializer_rejects_both_template_and_subject_body():
    serializer = EmailMessageQueueSerializer()
    with pytest.raises(serializers.ValidationError):
        serializer.validate({"template": object(), "subject": "S", "body": "B"})


def test_queue_serializer_rejects_neither():
    serializer = EmailMessageQueueSerializer()
    with pytest.raises(serializers.ValidationError):
        serializer.validate({})


def test_queue_serializer_accepts_template_only():
    serializer = EmailMessageQueueSerializer()
    attrs = {"template": object()}
    assert serializer.validate(attrs) == attrs


def test_queue_serializer_accepts_subject_and_body_only():
    serializer = EmailMessageQueueSerializer()
    attrs = {"subject": "S", "body": "B"}
    assert serializer.validate(attrs) == attrs


# --------------------------------------------------------------------------
# Requires database — full serializer validation (FK fields query the DB)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_queue_serializer_full_validation_with_template(email_template):
    serializer = EmailMessageQueueSerializer(data={"to_email": "a@example.com", "template": email_template.pk})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_notification_serializer_full_validation(employee):
    serializer = NotificationSerializer(data={"recipient": employee.pk, "notification_type": "INFO", "title": "Hi"})
    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
def test_email_message_serializer_related_object_output(customer, employee):
    from apps.communications.services import queue_email

    message = queue_email("a@example.com", subject="Hi", body="Hi", owner=employee, related_object=customer)
    data = EmailMessageSerializer(message).data

    assert data["related_object"]["label"] == str(customer)
