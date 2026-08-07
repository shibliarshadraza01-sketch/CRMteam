"""CP18: URL routing tests — no database needed."""
from django.urls import reverse


def test_all_four_resources_resolve():
    for basename in ("integration", "api-key", "webhook-endpoint", "webhook-delivery"):
        assert reverse(f"integrations:{basename}-list")
        assert reverse(f"integrations:{basename}-detail", args=[1])


def test_restore_and_hard_delete_actions_resolve_for_writable_resources():
    for basename in ("integration", "api-key", "webhook-endpoint"):
        assert reverse(f"integrations:{basename}-restore", args=[1]).endswith("/restore/")
        assert reverse(f"integrations:{basename}-hard-delete", args=[1]).endswith("/hard-delete/")


def test_expected_url_paths():
    assert reverse("integrations:integration-list") == "/api/v1/integrations/integrations/"
    assert reverse("integrations:api-key-list") == "/api/v1/integrations/api-keys/"
    assert reverse("integrations:webhook-endpoint-list") == "/api/v1/integrations/webhook-endpoints/"
    assert reverse("integrations:webhook-delivery-list") == "/api/v1/integrations/webhook-deliveries/"


def test_apikey_rotate_and_revoke_actions_resolve():
    assert reverse("integrations:api-key-rotate", args=[1]).endswith("/rotate/")
    assert reverse("integrations:api-key-revoke", args=[1]).endswith("/revoke/")


def test_webhookendpoint_regenerate_secret_and_deliver_actions_resolve():
    assert reverse("integrations:webhook-endpoint-regenerate-secret", args=[1]).endswith("/regenerate-secret/")
    assert reverse("integrations:webhook-endpoint-deliver", args=[1]).endswith("/deliver/")
