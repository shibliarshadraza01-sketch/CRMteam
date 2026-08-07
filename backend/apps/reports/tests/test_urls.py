"""CP16: URL routing tests — no database needed."""
from django.urls import reverse


def test_all_four_resources_resolve():
    for basename in ("saved-report", "report-execution", "dashboard", "dashboard-widget"):
        assert reverse(f"reports:{basename}-list")
        assert reverse(f"reports:{basename}-detail", args=[1])


def test_restore_and_hard_delete_actions_resolve_for_writable_resources():
    for basename in ("saved-report", "dashboard", "dashboard-widget"):
        assert reverse(f"reports:{basename}-restore", args=[1]).endswith("/restore/")
        assert reverse(f"reports:{basename}-hard-delete", args=[1]).endswith("/hard-delete/")


def test_expected_url_paths():
    assert reverse("reports:saved-report-list") == "/api/v1/reports/saved-reports/"
    assert reverse("reports:report-execution-list") == "/api/v1/reports/report-executions/"
    assert reverse("reports:dashboard-list") == "/api/v1/reports/dashboards/"
    assert reverse("reports:dashboard-widget-list") == "/api/v1/reports/dashboard-widgets/"


def test_saved_report_execute_action_resolves():
    assert reverse("reports:saved-report-execute", args=[1]).endswith("/execute/")


def test_dashboard_set_default_action_resolves():
    assert reverse("reports:dashboard-set-default", args=[1]).endswith("/set-default/")
