"""CP15: tests for apps/communications/models.py."""
import pytest

from apps.communications.models import CommunicationLog, EmailMessage, EmailTemplate, Notification

# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_email_template_inherits_soft_delete_and_timestamps_from_core():
    field_names = {f.name for f in EmailTemplate._meta.get_fields()}
    assert {"created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at"} <= field_names


def test_email_template_name_is_unique():
    assert EmailTemplate._meta.get_field("name").unique is True


def test_email_template_str_returns_name():
    assert str(EmailTemplate(name="Welcome")) == "Welcome"


def test_email_message_has_generic_relation_fields_reused_from_activities():
    from apps.activities.models import RelatedToEntityModel

    assert issubclass(EmailMessage, RelatedToEntityModel)
    field_names = {f.name for f in EmailMessage._meta.get_fields()}
    assert {"content_type", "object_id", "related_object"} <= field_names


def test_notification_and_communicationlog_also_reuse_the_mixin():
    from apps.activities.models import RelatedToEntityModel

    assert issubclass(Notification, RelatedToEntityModel)
    assert issubclass(CommunicationLog, RelatedToEntityModel)


def test_email_message_status_defaults_to_queued():
    assert EmailMessage._meta.get_field("status").default == EmailMessage.Status.QUEUED


def test_email_message_str_includes_subject_and_status_but_never_the_recipient():
    """``__str__`` deliberately omits ``to_email``: CP14's
    ``RelatedObjectMixin`` renders ``str(target)`` into an employee-visible
    ``related_object.label``, and Django's admin change list renders it
    too, so any PII here would leak through both.
    """
    message = EmailMessage(subject="Hi", to_email="a@example.com", status=EmailMessage.Status.QUEUED)
    assert "Hi" in str(message)
    assert "a@example.com" not in str(message)
    assert "QUEUED" in str(message)


def test_notification_recipient_is_not_nullable():
    field = Notification._meta.get_field("recipient")
    assert field.null is False


def test_notification_owner_property_delegates_to_recipient():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="recipient@example.com")
    notification = Notification(recipient=user)
    assert notification.owner is user


def test_notification_str_returns_title():
    assert str(Notification(title="Ping")) == "Ping"


def test_communicationlog_owner_property_delegates_to_actor():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User(email="actor@example.com")
    log = CommunicationLog(actor=user)
    assert log.owner is user


def test_communicationlog_str_includes_channel_and_summary():
    log = CommunicationLog(channel=CommunicationLog.Channel.EMAIL, summary="Sent welcome email")
    assert "EMAIL" in str(log)
    assert "Sent welcome email" in str(log)


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_email_template_create_and_retrieve():
    template = EmailTemplate.objects.create(name="Reminder", subject="Reminder", body="Don't forget")
    assert EmailTemplate.objects.get(pk=template.pk).is_active is True


@pytest.mark.django_db
def test_email_template_name_uniqueness_enforced():
    from django.db import IntegrityError

    EmailTemplate.objects.create(name="Dup", subject="A", body="A")
    with pytest.raises(IntegrityError):
        EmailTemplate.objects.create(name="Dup", subject="B", body="B")


@pytest.mark.django_db
def test_email_message_attaches_to_customer_via_generic_fk(customer, employee):
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(customer)
    message = EmailMessage.objects.create(
        owner=employee, to_email="x@example.com", subject="Hi", body="Hi",
        content_type=content_type, object_id=customer.pk,
    )
    assert message.related_object == customer


@pytest.mark.django_db
def test_notification_manager_has_access_true_for_managed_recipient(manager, employee, organization):
    from apps.organization.models import Department, Membership, Team

    department = Department.objects.create(organization=organization, name="Support")
    team = Team.objects.create(department=department, name="Support Team", manager=manager)
    Membership.objects.create(team=team, user=employee)

    notification = Notification.objects.create(recipient=employee, title="Ping")

    assert notification.manager_has_access(manager) is True


@pytest.mark.django_db
def test_deleting_email_template_sets_null_on_message(email_template, employee):
    message = EmailMessage.objects.create(
        template=email_template, owner=employee, to_email="x@example.com", subject="Hi", body="Hi"
    )
    email_template.delete()
    message.refresh_from_db()
    assert message.template_id is None
