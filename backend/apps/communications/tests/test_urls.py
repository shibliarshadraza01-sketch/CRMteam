"""CP15: URL routing tests — no database needed."""
from django.urls import reverse


def test_all_four_resources_resolve():
    for basename in ("email-template", "email-message", "notification", "communication-log"):
        assert reverse(f"communications:{basename}-list")
        assert reverse(f"communications:{basename}-detail", args=[1])


def test_restore_and_hard_delete_actions_resolve_for_writable_resources():
    for basename in ("email-template", "email-message", "notification"):
        assert reverse(f"communications:{basename}-restore", args=[1]).endswith("/restore/")
        assert reverse(f"communications:{basename}-hard-delete", args=[1]).endswith("/hard-delete/")


def test_expected_url_paths():
    assert reverse("communications:email-template-list") == "/api/v1/communications/email-templates/"
    assert reverse("communications:email-message-list") == "/api/v1/communications/email-messages/"
    assert reverse("communications:notification-list") == "/api/v1/communications/notifications/"
    assert reverse("communications:communication-log-list") == "/api/v1/communications/communication-logs/"


def test_email_message_send_action_resolves():
    assert reverse("communications:email-message-send", args=[1]).endswith("/send/")


def test_notification_mark_read_and_unread_actions_resolve():
    assert reverse("communications:notification-mark-read", args=[1]).endswith("/mark-read/")
    assert reverse("communications:notification-mark-unread", args=[1]).endswith("/mark-unread/")
