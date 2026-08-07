"""CP17: URL routing tests — no database needed."""
from django.urls import reverse


def test_all_four_resources_resolve():
    for basename in ("workflow", "workflow-trigger", "workflow-action", "workflow-execution"):
        assert reverse(f"workflows:{basename}-list")
        assert reverse(f"workflows:{basename}-detail", args=[1])


def test_restore_and_hard_delete_actions_resolve_for_writable_resources():
    for basename in ("workflow", "workflow-trigger", "workflow-action"):
        assert reverse(f"workflows:{basename}-restore", args=[1]).endswith("/restore/")
        assert reverse(f"workflows:{basename}-hard-delete", args=[1]).endswith("/hard-delete/")


def test_expected_url_paths():
    assert reverse("workflows:workflow-list") == "/api/v1/workflows/workflows/"
    assert reverse("workflows:workflow-trigger-list") == "/api/v1/workflows/triggers/"
    assert reverse("workflows:workflow-action-list") == "/api/v1/workflows/actions/"
    assert reverse("workflows:workflow-execution-list") == "/api/v1/workflows/executions/"


def test_workflow_execute_action_resolves():
    assert reverse("workflows:workflow-execute", args=[1]).endswith("/execute/")
