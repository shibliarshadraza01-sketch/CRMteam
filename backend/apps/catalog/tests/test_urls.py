"""CP13: URL routing tests — no database needed."""
from django.urls import reverse


def test_all_four_resources_resolve():
    for basename in ("product", "service", "pricebook", "pricebook-entry"):
        assert reverse(f"catalog:{basename}-list")
        assert reverse(f"catalog:{basename}-detail", args=[1])


def test_restore_and_hard_delete_actions_resolve_for_every_resource():
    for basename in ("product", "service", "pricebook", "pricebook-entry"):
        assert reverse(f"catalog:{basename}-restore", args=[1]).endswith("/restore/")
        assert reverse(f"catalog:{basename}-hard-delete", args=[1]).endswith("/hard-delete/")


def test_expected_url_paths():
    assert reverse("catalog:product-list") == "/api/v1/catalog/products/"
    assert reverse("catalog:service-list") == "/api/v1/catalog/services/"
    assert reverse("catalog:pricebook-list") == "/api/v1/catalog/pricebooks/"
    assert reverse("catalog:pricebook-entry-list") == "/api/v1/catalog/pricebook-entries/"
