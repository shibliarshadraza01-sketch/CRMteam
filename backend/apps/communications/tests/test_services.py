"""CP15: tests for apps/communications/services.py."""
import pytest

from apps.communications.models import CommunicationLog, EmailMessage, EmailTemplate, Notification
from apps.communications.services import (
    create_notification,
    log_communication,
    managed_user_ids,
    mark_notification_read,
    mark_notification_unread,
    queue_email,
    render_template,
    scope_queryset_for_user,
    send_queued_email,
)

# --------------------------------------------------------------------------
# No database required — pure text substitution
# --------------------------------------------------------------------------


def test_render_template_substitutes_known_placeholders():
    template = EmailTemplate(subject="Hi {{name}}", body="Welcome, {{name}}! Your plan is {{plan}}.")
    subject, body = render_template(template, {"name": "Ada", "plan": "Pro"})
    assert subject == "Hi Ada"
    assert body == "Welcome, Ada! Your plan is Pro."


def test_render_template_leaves_unknown_placeholders_unchanged():
    template = EmailTemplate(subject="Hi {{name}}", body="{{unknown}} stays literal")
    subject, body = render_template(template, {"name": "Ada"})
    assert subject == "Hi Ada"
    assert body == "{{unknown}} stays literal"


def test_render_template_with_no_context_leaves_everything_unchanged():
    template = EmailTemplate(subject="Hi {{name}}", body="Body {{x}}")
    subject, body = render_template(template)
    assert subject == "Hi {{name}}"
    assert body == "Body {{x}}"


def test_managed_user_ids_and_scope_queryset_for_user_are_reexported_from_crm():
    from apps.crm import services as crm_services

    assert managed_user_ids is crm_services.managed_user_ids
    assert scope_queryset_for_user is crm_services.scope_queryset_for_user


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_queue_email_from_template(email_template):
    message = queue_email("to@example.com", template=email_template, context={"name": "Ada"})
    assert message.subject == "Welcome, Ada!"
    assert "Ada" in message.body
    assert message.status == EmailMessage.Status.QUEUED


@pytest.mark.django_db
def test_queue_email_from_explicit_subject_and_body():
    message = queue_email("to@example.com", subject="Hi", body="There")
    assert message.subject == "Hi"
    assert message.body == "There"


@pytest.mark.django_db
def test_queue_email_rejects_neither_template_nor_subject_body():
    with pytest.raises(ValueError):
        queue_email("to@example.com")


@pytest.mark.django_db
def test_queue_email_attaches_related_object(customer):
    from django.contrib.contenttypes.models import ContentType

    message = queue_email("to@example.com", subject="Hi", body="There", related_object=customer)
    assert message.content_type == ContentType.objects.get_for_model(customer)
    assert message.object_id == customer.pk


@pytest.mark.django_db
def test_send_queued_email_success_marks_sent_and_logs(email_message):
    def fake_send(message):
        return None

    send_queued_email(email_message, send_func=fake_send)

    email_message.refresh_from_db()
    assert email_message.status == EmailMessage.Status.SENT
    assert email_message.sent_at is not None
    assert CommunicationLog.objects.filter(channel=CommunicationLog.Channel.EMAIL).exists()


@pytest.mark.django_db
def test_send_queued_email_failure_marks_failed_and_does_not_raise(email_message):
    def failing_send(message):
        raise RuntimeError("SMTP down")

    result = send_queued_email(email_message, send_func=failing_send)

    assert result.status == EmailMessage.Status.FAILED
    assert result.error_message == "SMTP down"


@pytest.mark.django_db
def test_send_queued_email_default_send_func_uses_configured_email_backend(email_message):
    """No ``send_func`` override — exercises the REAL delivery path
    (``_default_send_func`` -> Django's own ``send_mail()``) rather than
    an injected fake, proving the SendGrid/EMAIL_BACKEND settings wiring
    (final-completion-pass: config/settings/{development,production}.py)
    is actually reachable end-to-end, not just declared. Django's test
    runner forces ``EMAIL_BACKEND`` to locmem for the duration of any
    test regardless of the real per-environment setting, capturing every
    "sent" message in ``django.core.mail.outbox`` — this is what proves
    the message really flowed through Django's mail system, not just
    that some function was called.
    """
    from django.core import mail

    send_queued_email(email_message)

    email_message.refresh_from_db()
    assert email_message.status == EmailMessage.Status.SENT
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [email_message.to_email]
    assert mail.outbox[0].subject == email_message.subject


@pytest.mark.django_db
def test_send_queued_email_rejects_already_sent(email_message):
    send_queued_email(email_message, send_func=lambda message: None)
    with pytest.raises(ValueError):
        send_queued_email(email_message, send_func=lambda message: None)


@pytest.mark.django_db
def test_create_notification_and_logs_communication(employee):
    notification = create_notification(employee, Notification.NotificationType.INFO, "Hello")
    assert notification.recipient_id == employee.id
    assert CommunicationLog.objects.filter(channel=CommunicationLog.Channel.NOTIFICATION).exists()


@pytest.mark.django_db
def test_create_notification_attaches_related_object(customer, employee):
    notification = create_notification(
        employee, Notification.NotificationType.INFO, "Hello", related_object=customer
    )
    assert notification.related_object == customer


@pytest.mark.django_db
def test_mark_notification_read_and_unread(notification):
    mark_notification_read(notification)
    notification.refresh_from_db()
    assert notification.is_read is True
    assert notification.read_at is not None

    mark_notification_unread(notification)
    notification.refresh_from_db()
    assert notification.is_read is False
    assert notification.read_at is None


@pytest.mark.django_db
def test_mark_notification_read_is_idempotent(notification):
    mark_notification_read(notification)
    mark_notification_read(notification)  # must not raise
    notification.refresh_from_db()
    assert notification.is_read is True


@pytest.mark.django_db
def test_log_communication_creates_entry(customer, employee):
    log = log_communication(channel=CommunicationLog.Channel.OTHER, summary="Test", actor=employee, related_object=customer)
    assert log.summary == "Test"
    assert log.related_object == customer
