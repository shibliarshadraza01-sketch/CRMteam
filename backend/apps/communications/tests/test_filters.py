"""CP15: tests for apps/communications/filters.py."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.communications.filters import (
    CallFilterSet,
    CommunicationLogFilterSet,
    EmailMessageFilterSet,
    NotificationFilterSet,
    WhatsAppMessageFilterSet,
)
from apps.communications.models import Call, CommunicationLog, EmailMessage, Notification, WhatsAppMessage

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_email_message_filterset_declares_expected_fields():
    assert set(EmailMessageFilterSet.Meta.fields) == {
        "status", "direction", "owner", "template", "content_type", "object_id",
    }


def test_call_filterset_declares_expected_fields():
    assert set(CallFilterSet.Meta.fields) == {"status", "direction", "owner", "content_type", "object_id"}


def test_whatsapp_filterset_declares_expected_fields():
    assert set(WhatsAppMessageFilterSet.Meta.fields) == {"status", "direction", "owner", "customer"}


def test_every_communications_filterset_exposes_a_date_range_pair():
    """The audit spec's "filter by date/time range" requirement, asserted
    per FilterSet so a future channel can't quietly ship without one.
    """
    expected = {
        EmailMessageFilterSet: ["created_from", "created_to", "sent_from", "sent_to"],
        CallFilterSet: ["started_from", "started_to", "created_from", "created_to"],
        WhatsAppMessageFilterSet: ["created_from", "created_to"],
        CommunicationLogFilterSet: ["occurred_from", "occurred_to"],
    }
    for filterset_class, names in expected.items():
        declared = filterset_class.base_filters
        for name in names:
            assert name in declared, f"{filterset_class.__name__} is missing {name}"


def test_notification_filterset_declares_expected_fields():
    assert set(NotificationFilterSet.Meta.fields) == {
        "notification_type", "is_read", "recipient", "content_type", "object_id",
    }


def test_status_filter_builds_query_without_hitting_db():
    filterset = EmailMessageFilterSet(data={"status": "SENT"}, queryset=EmailMessage.objects.all())
    assert filterset.is_valid()
    assert len(filterset.qs.query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_status_filter_matches_real_rows(employee):
    sent = EmailMessage.objects.create(
        owner=employee, to_email="a@example.com", subject="A", body="A", status=EmailMessage.Status.SENT
    )
    EmailMessage.objects.create(owner=employee, to_email="b@example.com", subject="B", body="B")

    filterset = EmailMessageFilterSet(data={"status": "SENT"}, queryset=EmailMessage.objects.all())

    assert list(filterset.qs) == [sent]


@pytest.mark.django_db
def test_is_read_filter_matches_real_rows(employee):
    unread = Notification.objects.create(recipient=employee, title="Unread")
    Notification.objects.create(recipient=employee, title="Read", is_read=True)

    filterset = NotificationFilterSet(data={"is_read": "false"}, queryset=Notification.objects.all())

    assert list(filterset.qs) == [unread]


@pytest.mark.django_db
def test_call_filterset_narrows_by_status_direction_and_owner(employee, other_employee):
    mine = Call.objects.create(
        owner=employee,
        direction=Call.Direction.OUTBOUND,
        from_number="+10000000000",
        to_number="+19999999999",
        status=Call.Status.COMPLETED,
    )
    Call.objects.create(
        owner=other_employee,
        direction=Call.Direction.OUTBOUND,
        from_number="+10000000000",
        to_number="+18888888888",
        status=Call.Status.COMPLETED,
    )
    Call.objects.create(
        owner=employee,
        direction=Call.Direction.INBOUND,
        from_number="+17777777777",
        to_number="+10000000000",
        status=Call.Status.FAILED,
    )

    filterset = CallFilterSet(
        data={"status": "COMPLETED", "direction": "OUTBOUND", "owner": employee.pk},
        queryset=Call.objects.all(),
    )

    assert list(filterset.qs) == [mine]


@pytest.mark.django_db
def test_whatsapp_filterset_narrows_by_status_and_direction(employee):
    delivered = WhatsAppMessage.objects.create(
        owner=employee,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        sender="1",
        receiver="2",
        message="hi",
        status=WhatsAppMessage.Status.DELIVERED,
    )
    WhatsAppMessage.objects.create(
        owner=employee,
        direction=WhatsAppMessage.Direction.INBOUND,
        sender="2",
        receiver="1",
        message="hello",
        status=WhatsAppMessage.Status.DELIVERED,
    )

    filterset = WhatsAppMessageFilterSet(
        data={"status": "DELIVERED", "direction": "OUTBOUND"}, queryset=WhatsAppMessage.objects.all()
    )

    assert list(filterset.qs) == [delivered]


@pytest.mark.django_db
def test_communication_log_date_range_filter_excludes_rows_outside_the_window(employee):
    now = timezone.now()
    inside = CommunicationLog.objects.create(
        channel=CommunicationLog.Channel.EMAIL, summary="inside", actor=employee, occurred_at=now
    )
    CommunicationLog.objects.create(
        channel=CommunicationLog.Channel.EMAIL,
        summary="outside",
        actor=employee,
        occurred_at=now - timedelta(days=10),
    )

    filterset = CommunicationLogFilterSet(
        data={
            "occurred_from": (now - timedelta(days=1)).isoformat(),
            "occurred_to": (now + timedelta(days=1)).isoformat(),
        },
        queryset=CommunicationLog.objects.all(),
    )

    assert filterset.is_valid(), filterset.errors
    assert list(filterset.qs) == [inside]
