"""CP10: URL routing tests. Reversing a URL name only needs the resolved
URLconf (loaded once at Django setup) — no database involved.
"""
from django.urls import reverse


def test_customer_list_and_detail_urls_resolve():
    assert reverse("crm:customer-list") == "/api/v1/crm/customers/"
    assert reverse("crm:customer-detail", args=[1]) == "/api/v1/crm/customers/1/"


def test_lead_list_and_detail_urls_resolve():
    assert reverse("crm:lead-list") == "/api/v1/crm/leads/"
    assert reverse("crm:lead-detail", args=[1]) == "/api/v1/crm/leads/1/"


def test_contact_list_and_detail_urls_resolve():
    assert reverse("crm:contact-list") == "/api/v1/crm/contacts/"
    assert reverse("crm:contact-detail", args=[1]) == "/api/v1/crm/contacts/1/"


def test_address_list_and_detail_urls_resolve():
    assert reverse("crm:address-list") == "/api/v1/crm/addresses/"
    assert reverse("crm:address-detail", args=[1]) == "/api/v1/crm/addresses/1/"


def test_restore_and_hard_delete_actions_resolve_for_every_resource():
    for basename in ("customer", "lead", "contact", "address"):
        assert reverse(f"crm:{basename}-restore", args=[1]).endswith("/restore/")
        assert reverse(f"crm:{basename}-hard-delete", args=[1]).endswith("/hard-delete/")
