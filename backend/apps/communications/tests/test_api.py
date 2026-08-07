"""CP15: end-to-end tests for the communications API. Requires a real
database.
"""
import pytest

from apps.communications.models import CommunicationLog, EmailMessage, EmailTemplate, Notification

pytestmark = pytest.mark.django_db

EMAIL_TEMPLATES_URL = "/api/v1/communications/email-templates/"
EMAIL_MESSAGES_URL = "/api/v1/communications/email-messages/"
NOTIFICATIONS_URL = "/api/v1/communications/notifications/"
COMMUNICATION_LOGS_URL = "/api/v1/communications/communication-logs/"


def _detail(url, pk):
    return f"{url}{pk}/"


# --------------------------------------------------------------------------
# EmailTemplate — shared reference data, read/write split (CP13's model)
# --------------------------------------------------------------------------


def test_unauthenticated_denied(api_client):
    response = api_client.get(EMAIL_TEMPLATES_URL)
    assert response.status_code == 401


def test_employee_can_read_email_templates(api_client, employee, email_template):
    api_client.force_authenticate(employee)
    response = api_client.get(EMAIL_TEMPLATES_URL)
    assert response.status_code == 200


def test_employee_cannot_create_email_template(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(EMAIL_TEMPLATES_URL, {"name": "X", "subject": "X", "body": "X"})
    assert response.status_code == 403


def test_manager_can_create_email_template(api_client, manager):
    api_client.force_authenticate(manager)
    response = api_client.post(EMAIL_TEMPLATES_URL, {"name": "X", "subject": "X", "body": "X"})
    assert response.status_code == 201


# --------------------------------------------------------------------------
# EmailMessage — ownership-scoped, custom create() + send action
# --------------------------------------------------------------------------


def test_employee_can_queue_email_from_explicit_subject_body(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(EMAIL_MESSAGES_URL, {"to_email": "x@example.com", "subject": "Hi", "body": "There"})
    assert response.status_code == 201
    assert response.data["status"] == "QUEUED"
    assert response.data["owner"] == employee.id


def test_employee_can_queue_email_from_template(api_client, employee, email_template):
    api_client.force_authenticate(employee)
    response = api_client.post(
        EMAIL_MESSAGES_URL, {"to_email": "x@example.com", "template": email_template.pk, "context": {"name": "Ada"}}
    )
    assert response.status_code == 201
    assert response.data["subject"] == "Welcome, Ada!"


def test_queue_email_rejects_both_template_and_subject(api_client, employee, email_template):
    api_client.force_authenticate(employee)
    response = api_client.post(
        EMAIL_MESSAGES_URL,
        {"to_email": "x@example.com", "template": email_template.pk, "subject": "Hi", "body": "There"},
    )
    assert response.status_code == 400


def test_employee_cannot_see_another_employees_email_message(api_client, employee, other_employee):
    EmailMessage.objects.create(owner=other_employee, to_email="a@example.com", subject="A", body="A")
    api_client.force_authenticate(employee)

    response = api_client.get(EMAIL_MESSAGES_URL)

    assert response.data["count"] == 0


def test_send_action_marks_message_sent(api_client, employee, email_message, monkeypatch):
    monkeypatch.setattr("apps.communications.services._default_send_func", lambda message: None)
    api_client.force_authenticate(employee)

    response = api_client.post(f"{_detail(EMAIL_MESSAGES_URL, email_message.pk)}send/")

    assert response.status_code == 200
    assert response.data["status"] == "SENT"


def test_send_action_rejects_already_sent(api_client, employee, email_message, monkeypatch):
    monkeypatch.setattr("apps.communications.services._default_send_func", lambda message: None)
    api_client.force_authenticate(employee)
    api_client.post(f"{_detail(EMAIL_MESSAGES_URL, email_message.pk)}send/")

    response = api_client.post(f"{_detail(EMAIL_MESSAGES_URL, email_message.pk)}send/")

    assert response.status_code == 400


# --------------------------------------------------------------------------
# Notification — recipient-scoped, mark-read/unread actions
# --------------------------------------------------------------------------


def test_create_notification_for_another_user(api_client, employee, other_employee):
    api_client.force_authenticate(employee)
    response = api_client.post(
        NOTIFICATIONS_URL, {"recipient": other_employee.pk, "notification_type": "INFO", "title": "Hi"}
    )
    assert response.status_code == 201
    assert response.data["recipient"] == other_employee.pk


def test_employee_cannot_see_someone_elses_notification(api_client, employee, other_employee):
    Notification.objects.create(recipient=other_employee, title="Not mine")
    api_client.force_authenticate(employee)

    response = api_client.get(NOTIFICATIONS_URL)

    assert response.data["count"] == 0


def test_mark_read_action(api_client, employee, notification):
    api_client.force_authenticate(employee)
    response = api_client.post(f"{_detail(NOTIFICATIONS_URL, notification.pk)}mark-read/")
    assert response.status_code == 200
    assert response.data["is_read"] is True


def test_mark_unread_action(api_client, employee, notification):
    api_client.force_authenticate(employee)
    api_client.post(f"{_detail(NOTIFICATIONS_URL, notification.pk)}mark-read/")

    response = api_client.post(f"{_detail(NOTIFICATIONS_URL, notification.pk)}mark-unread/")

    assert response.status_code == 200
    assert response.data["is_read"] is False


# --------------------------------------------------------------------------
# CommunicationLog — read-only, system-populated only
# --------------------------------------------------------------------------


def test_communication_log_has_no_create_endpoint(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(COMMUNICATION_LOGS_URL, {"channel": "OTHER", "summary": "Fake"})
    assert response.status_code == 405


def test_communication_log_populated_automatically_by_notification_creation(api_client, employee, other_employee):
    api_client.force_authenticate(employee)
    api_client.post(NOTIFICATIONS_URL, {"recipient": other_employee.pk, "notification_type": "INFO", "title": "Hi"})

    assert CommunicationLog.objects.filter(channel=CommunicationLog.Channel.NOTIFICATION, summary="Hi").exists()


def test_employee_sees_only_their_own_communication_logs(api_client, employee, other_employee):
    from apps.communications.services import log_communication

    log_communication(channel=CommunicationLog.Channel.OTHER, summary="Mine", actor=employee)
    log_communication(channel=CommunicationLog.Channel.OTHER, summary="Not mine", actor=other_employee)
    api_client.force_authenticate(employee)

    response = api_client.get(COMMUNICATION_LOGS_URL)

    summaries = {row["summary"] for row in response.data["results"]}
    assert summaries == {"Mine"}


# --------------------------------------------------------------------------
# Search / filter / ordering / pagination
# --------------------------------------------------------------------------


def test_search_email_templates_by_name(api_client, employee):
    EmailTemplate.objects.create(name="Renewal Reminder", subject="X", body="X")
    EmailTemplate.objects.create(name="Other", subject="X", body="X")

    api_client.force_authenticate(employee)
    response = api_client.get(EMAIL_TEMPLATES_URL, {"search": "Renewal"})

    names = {row["name"] for row in response.data["results"]}
    assert names == {"Renewal Reminder"}


def test_pagination_default_page_size_is_20(api_client, manager):
    for i in range(25):
        EmailTemplate.objects.create(name=f"Template {i:03d}", subject="X", body="X")
    api_client.force_authenticate(manager)

    response = api_client.get(EMAIL_TEMPLATES_URL)

    assert len(response.data["results"]) == 20
    assert response.data["count"] == 25
