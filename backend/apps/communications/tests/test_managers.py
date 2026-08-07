"""CP15: tests for the querysets on apps/communications/models.py."""
import pytest

from apps.communications.models import EmailMessage, EmailTemplate, Notification

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_email_template_active_filters_is_deleted_and_is_active_without_hitting_db():
    where_sql = str(EmailTemplate.objects.active().query.where)
    assert "is_deleted" in where_sql
    assert "is_active" in where_sql


def test_email_message_queued_filters_on_status_without_hitting_db():
    where_sql = str(EmailMessage.objects.queued().query.where)
    assert "status" in where_sql


def test_notification_unread_filters_on_is_read_without_hitting_db():
    where_sql = str(Notification.objects.unread().query.where)
    assert "is_read" in where_sql


def test_notification_for_recipient_builds_filter_without_hitting_db():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert len(Notification.objects.for_recipient(User(pk=1)).query.where) > 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_active_email_template_manager_excludes_deleted():
    active = EmailTemplate.objects.create(name="Active", subject="S", body="B")
    deleted = EmailTemplate.objects.create(name="Deleted", subject="S", body="B")
    deleted.soft_delete()

    assert list(EmailTemplate.active_objects.values_list("name", flat=True)) == ["Active"]


@pytest.mark.django_db
def test_email_message_queued_matches_real_rows(employee):
    queued = EmailMessage.objects.create(owner=employee, to_email="a@example.com", subject="A", body="A")
    EmailMessage.objects.create(
        owner=employee, to_email="b@example.com", subject="B", body="B", status=EmailMessage.Status.SENT
    )

    assert list(EmailMessage.objects.queued()) == [queued]


@pytest.mark.django_db
def test_email_message_for_entity_matches_real_rows(customer, employee):
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(customer)
    matching = EmailMessage.objects.create(
        owner=employee, to_email="a@example.com", subject="A", body="A",
        content_type=content_type, object_id=customer.pk,
    )
    EmailMessage.objects.create(owner=employee, to_email="b@example.com", subject="B", body="B")

    assert list(EmailMessage.objects.for_entity(customer)) == [matching]


@pytest.mark.django_db
def test_notification_unread_and_for_recipient_match_real_rows(employee, other_employee):
    unread = Notification.objects.create(recipient=employee, title="Unread")
    Notification.objects.create(recipient=employee, title="Read", is_read=True)
    Notification.objects.create(recipient=other_employee, title="Not mine")

    result = Notification.objects.for_recipient(employee).unread()

    assert list(result) == [unread]
