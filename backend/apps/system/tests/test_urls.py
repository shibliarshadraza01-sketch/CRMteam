"""CP19: URL routing tests — no database needed."""
from django.urls import reverse


def test_all_four_resources_resolve():
    for basename in ("audit-log", "system-setting", "feature-flag", "background-job"):
        assert reverse(f"system:{basename}-list")
        assert reverse(f"system:{basename}-detail", args=[1])


def test_restore_and_hard_delete_actions_resolve_for_writable_resources():
    for basename in ("system-setting", "feature-flag", "background-job"):
        assert reverse(f"system:{basename}-restore", args=[1]).endswith("/restore/")
        assert reverse(f"system:{basename}-hard-delete", args=[1]).endswith("/hard-delete/")


def test_expected_url_paths():
    assert reverse("system:audit-log-list") == "/api/v1/system/audit-logs/"
    assert reverse("system:system-setting-list") == "/api/v1/system/settings/"
    assert reverse("system:feature-flag-list") == "/api/v1/system/feature-flags/"
    assert reverse("system:background-job-list") == "/api/v1/system/background-jobs/"


def test_backgroundjob_lifecycle_actions_resolve():
    assert reverse("system:background-job-start", args=[1]).endswith("/start/")
    assert reverse("system:background-job-complete", args=[1]).endswith("/complete/")
    assert reverse("system:background-job-fail", args=[1]).endswith("/fail/")
