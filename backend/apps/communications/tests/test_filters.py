"""CP15: tests for apps/communications/filters.py."""
import pytest

from apps.communications.filters import EmailMessageFilterSet, NotificationFilterSet
from apps.communications.models import EmailMessage, Notification

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_email_message_filterset_declares_expected_fields():
    assert set(EmailMessageFilterSet.Meta.fields) == {"status", "owner", "template", "content_type", "object_id"}


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
