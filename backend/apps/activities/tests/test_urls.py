"""CP14: URL routing tests — no database needed."""
from django.urls import reverse


def test_all_four_resources_resolve():
    for basename in ("task", "event", "activity-log", "reminder"):
        assert reverse(f"activities:{basename}-list")
        assert reverse(f"activities:{basename}-detail", args=[1])


def test_restore_and_hard_delete_actions_resolve_for_every_resource():
    for basename in ("task", "event", "activity-log", "reminder"):
        assert reverse(f"activities:{basename}-restore", args=[1]).endswith("/restore/")
        assert reverse(f"activities:{basename}-hard-delete", args=[1]).endswith("/hard-delete/")


def test_expected_url_paths():
    assert reverse("activities:task-list") == "/api/v1/activities/tasks/"
    assert reverse("activities:event-list") == "/api/v1/activities/events/"
    assert reverse("activities:activity-log-list") == "/api/v1/activities/activity-logs/"
    assert reverse("activities:reminder-list") == "/api/v1/activities/reminders/"


def test_task_custom_actions_resolve():
    assert reverse("activities:task-complete", args=[1]).endswith("/complete/")
    assert reverse("activities:task-cancel", args=[1]).endswith("/cancel/")
    assert reverse("activities:task-reassign", args=[1]).endswith("/reassign/")


def test_event_occurrences_action_resolves():
    assert reverse("activities:event-occurrences", args=[1]).endswith("/occurrences/")


def test_reminder_mark_sent_action_resolves():
    assert reverse("activities:reminder-mark-sent", args=[1]).endswith("/mark-sent/")


def test_timeline_endpoint_resolves():
    assert reverse("activities:timeline") == "/api/v1/activities/timeline/"
