"""Staff-management pass: only a Super Admin may author notifications.

Manager and Employee still RECEIVE notifications, list/retrieve their own,
and mark them read/unread — they simply cannot create, edit, or delete a
notification record through the API. System-generated notifications
(``services.create_notification()``) are unaffected.
"""
import pytest

from apps.communications.models import CommunicationLog, Notification
from apps.communications.services import create_notification

NOTIFICATIONS_URL = "/api/v1/communications/notifications/"


def _payload(recipient):
    return {"recipient": recipient.pk, "notification_type": "INFO", "title": "Scheduled ping"}


@pytest.mark.parametrize("role_fixture", ["employee", "manager"])
def test_non_super_admin_cannot_create_a_notification(api_client, request, role_fixture, other_employee):
    actor = request.getfixturevalue(role_fixture)
    api_client.force_authenticate(actor)

    response = api_client.post(NOTIFICATIONS_URL, _payload(other_employee))

    assert response.status_code == 403
    assert not Notification.objects.filter(title="Scheduled ping").exists()


def test_super_admin_can_create_a_notification(api_client, super_admin, employee):
    api_client.force_authenticate(super_admin)

    response = api_client.post(NOTIFICATIONS_URL, _payload(employee))

    assert response.status_code == 201


@pytest.mark.parametrize("role_fixture", ["employee", "manager"])
def test_non_super_admin_cannot_edit_a_notification(api_client, request, role_fixture):
    actor = request.getfixturevalue(role_fixture)
    notification = Notification.objects.create(recipient=actor, title="Mine")
    api_client.force_authenticate(actor)

    response = api_client.patch(f"{NOTIFICATIONS_URL}{notification.pk}/", {"title": "Edited"})

    assert response.status_code == 403
    notification.refresh_from_db()
    assert notification.title == "Mine"


@pytest.mark.parametrize("role_fixture", ["employee", "manager"])
def test_non_super_admin_cannot_delete_a_notification(api_client, request, role_fixture):
    actor = request.getfixturevalue(role_fixture)
    notification = Notification.objects.create(recipient=actor, title="Mine")
    api_client.force_authenticate(actor)

    response = api_client.delete(f"{NOTIFICATIONS_URL}{notification.pk}/")

    assert response.status_code == 403


@pytest.mark.parametrize("role_fixture", ["employee", "manager"])
def test_every_role_can_still_read_and_triage_their_own_notifications(api_client, request, role_fixture):
    actor = request.getfixturevalue(role_fixture)
    notification = Notification.objects.create(recipient=actor, title="Mine")
    api_client.force_authenticate(actor)

    assert api_client.get(NOTIFICATIONS_URL).data["count"] == 1
    assert api_client.get(f"{NOTIFICATIONS_URL}{notification.pk}/").status_code == 200

    read = api_client.post(f"{NOTIFICATIONS_URL}{notification.pk}/mark-read/")
    assert read.status_code == 200
    assert read.data["is_read"] is True

    unread = api_client.post(f"{NOTIFICATIONS_URL}{notification.pk}/mark-unread/")
    assert unread.status_code == 200
    assert unread.data["is_read"] is False


def test_system_generated_notifications_still_work(db, employee):
    """The restriction is on the CLIENT endpoint only — internal service
    calls (task due, payment overdue, follow-up scheduled, ...) bypass DRF
    permissions entirely and must keep working for every role.
    """
    notification = create_notification(employee, "INFO", "Task due", message="Follow up with Acme")

    assert Notification.objects.filter(pk=notification.pk, recipient=employee).exists()
    assert CommunicationLog.objects.filter(
        channel=CommunicationLog.Channel.NOTIFICATION, summary="Task due"
    ).exists()
