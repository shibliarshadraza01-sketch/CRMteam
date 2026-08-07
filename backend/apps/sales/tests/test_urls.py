"""CP12: URL routing tests — no database needed."""
from django.urls import reverse


def test_quote_and_invoice_list_and_detail_urls_resolve():
    assert reverse("sales:quote-list") == "/api/v1/sales/quotes/"
    assert reverse("sales:quote-detail", args=[1]) == "/api/v1/sales/quotes/1/"
    assert reverse("sales:invoice-list") == "/api/v1/sales/invoices/"
    assert reverse("sales:invoice-detail", args=[1]) == "/api/v1/sales/invoices/1/"


def test_quote_item_and_invoice_item_urls_resolve():
    assert reverse("sales:quote-item-list") == "/api/v1/sales/quote-items/"
    assert reverse("sales:invoice-item-list") == "/api/v1/sales/invoice-items/"


def test_quote_stage_transition_actions_resolve():
    for action in ("submit", "approve", "reject", "convert"):
        assert reverse(f"sales:quote-{action}", args=[1]) == f"/api/v1/sales/quotes/1/{action}/"


def test_invoice_actions_resolve():
    assert reverse("sales:invoice-mark-paid", args=[1]) == "/api/v1/sales/invoices/1/mark-paid/"
    assert reverse("sales:invoice-cancel", args=[1]) == "/api/v1/sales/invoices/1/cancel/"


def test_restore_and_hard_delete_actions_resolve_for_every_resource():
    for basename in ("quote", "invoice", "quote-item", "invoice-item"):
        assert reverse(f"sales:{basename}-restore", args=[1]).endswith("/restore/")
        assert reverse(f"sales:{basename}-hard-delete", args=[1]).endswith("/hard-delete/")
