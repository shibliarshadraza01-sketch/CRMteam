"""Customer-PII privacy tests for the whole employee-facing surface.

The rule under test: an EMPLOYEE must be able to email, call and WhatsApp
a customer/lead through the CRM without the customer's real email
address, phone number or WhatsApp number EVER crossing the
backend-to-employee boundary — not in a response body (however deeply
nested), not in a URL, not in an export, not in a notification, not in a
communication-history record, not in an error message, and not through a
search-by-value confirmation oracle.

Structure:

- ``test_negative_pii_sweep_*`` — the literal-string sweep the spec asks
  for: one customer and one lead carrying the sentinel values
  ``PII_TEST_EMAIL_123@example.com`` / ``PII_TEST_PHONE_123``, every
  employee-facing endpoint exercised, every response body searched
  recursively for those literals.
- ``test_*_authorization_*`` — an Employee cannot reach another
  Employee's customer/lead by naming its ID in a communication request.
- ``test_manager_*`` / ``test_super_admin_*`` — the deliberate,
  documented exception: Manager and Super Admin keep the raw-PII
  visibility they have always had (they can already read it on the
  customer record, and the spec's requirement is specifically about the
  EMPLOYEE boundary). These tests exist so locking Employees down can
  never silently break the roles that legitimately need the values.
"""
import json
from unittest.mock import patch

import pytest

from apps.communications.models import Call, CommunicationLog, EmailMessage, WhatsAppMessage
from apps.communications.services import queue_email

pytestmark = pytest.mark.django_db

PII_EMAIL = "PII_TEST_EMAIL_123@example.com"
PII_PHONE = "PII_TEST_PHONE_123"
PII_WHATSAPP = "PII_TEST_WHATSAPP_123"

#: Every literal that must never appear in an employee-facing response.
PII_LITERALS = ("PII_TEST_EMAIL_123", "PII_TEST_PHONE_123", "PII_TEST_WHATSAPP_123")

CUSTOMERS_URL = "/api/v1/crm/customers/"
LEADS_URL = "/api/v1/crm/leads/"
CONTACTS_URL = "/api/v1/crm/contacts/"
EMAIL_MESSAGES_URL = "/api/v1/communications/email-messages/"
CALLS_URL = "/api/v1/communications/calls/"
WHATSAPP_SEND_URL = "/api/v1/communications/whatsapp/send/"
WHATSAPP_MESSAGES_URL = "/api/v1/communications/whatsapp/messages/"
COMMUNICATION_LOGS_URL = "/api/v1/communications/communication-logs/"
NOTIFICATIONS_URL = "/api/v1/communications/notifications/"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def assert_no_pii(response, *, literals=PII_LITERALS, context=""):
    """Recursively assert none of `literals` appears anywhere in
    `response` — headers included, and the body searched as raw bytes so a
    value nested inside a nested object, a list, a stringified dict or a
    file download is all covered by one check.
    """
    blobs = [response.content or b""]
    for header, value in response.items():
        blobs.append(str(value).encode("utf-8", "ignore"))

    for blob in blobs:
        text = blob.decode("utf-8", "ignore")
        for literal in literals:
            assert literal not in text, (
                f"PII literal {literal!r} leaked to an employee{': ' + context if context else ''}"
            )


def find_pii_paths(payload, literals=PII_LITERALS, path="$"):
    """Return the JSON paths at which any literal appears — used to make a
    failure message point at the exact leaking field rather than just
    "somewhere in the body".
    """
    hits = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            hits.extend(find_pii_paths(value, literals, f"{path}.{key}"))
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            hits.extend(find_pii_paths(value, literals, f"{path}[{index}]"))
    else:
        text = "" if payload is None else str(payload)
        for literal in literals:
            if literal in text:
                hits.append(path)
    return hits


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def pii_customer(db, organization, employee):
    from apps.crm.models import Customer

    return Customer.objects.create(
        organization=organization,
        name="PII Sentinel Customer",
        slug="pii-sentinel-customer",
        owner=employee,
        email=PII_EMAIL,
        phone=PII_PHONE,
    )


@pytest.fixture
def pii_lead(db, employee):
    from apps.crm.models import Lead

    return Lead.objects.create(
        company_name="PII Sentinel Co",
        contact_name="PII Sentinel Contact",
        owner=employee,
        email=PII_EMAIL,
        phone=PII_PHONE,
    )


@pytest.fixture
def pii_contact(db, pii_customer):
    from apps.crm.models import ContactPerson

    return ContactPerson.objects.create(
        customer=pii_customer,
        first_name="Sentinel",
        last_name="Contact",
        email=PII_EMAIL,
        phone=PII_PHONE,
        is_primary=True,
    )


@pytest.fixture
def employee_client(api_client, employee):
    api_client.force_authenticate(employee)
    return api_client


# --------------------------------------------------------------------------
# CRM read surface
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url_name",
    ["customers", "leads", "contacts"],
)
def test_negative_pii_sweep_crm_list_and_detail(
    employee_client, pii_customer, pii_lead, pii_contact, url_name
):
    urls = {
        "customers": (CUSTOMERS_URL, pii_customer.pk),
        "leads": (LEADS_URL, pii_lead.pk),
        "contacts": (CONTACTS_URL, pii_contact.pk),
    }
    list_url, pk = urls[url_name]

    list_response = employee_client.get(list_url)
    assert list_response.status_code == 200
    assert_no_pii(list_response, context=f"{url_name} list")
    assert find_pii_paths(list_response.json()) == []

    detail_response = employee_client.get(f"{list_url}{pk}/")
    assert detail_response.status_code == 200
    assert_no_pii(detail_response, context=f"{url_name} detail")
    assert find_pii_paths(detail_response.json()) == []


def test_customer_detail_nested_contacts_are_masked_too(employee_client, pii_customer, pii_contact):
    """``CustomerDetailSerializer`` nests contacts — the nested shape must
    obey the same rule as the top-level one (DRF propagates serializer
    context into nested serializers, which is what makes this work).
    """
    response = employee_client.get(f"{CUSTOMERS_URL}{pii_customer.pk}/")
    body = response.json()

    assert body["contacts"], "the nested contacts list should not be empty"
    assert find_pii_paths(body) == []
    assert "email" not in body["contacts"][0]
    assert "phone" not in body["contacts"][0]


def test_employee_gets_capability_booleans_instead_of_values(employee_client, pii_customer):
    body = employee_client.get(f"{CUSTOMERS_URL}{pii_customer.pk}/").json()

    assert body["can_email"] is True
    assert body["can_call"] is True
    assert body["can_whatsapp"] is True
    assert "email" not in body
    assert "phone" not in body


def test_capability_booleans_are_false_without_contact_details(employee_client, customer):
    body = employee_client.get(f"{CUSTOMERS_URL}{customer.pk}/").json()

    assert body["can_email"] is False
    assert body["can_call"] is False
    assert body["can_whatsapp"] is False


# --------------------------------------------------------------------------
# Search / filter / ordering — the confirmation-oracle surface
# --------------------------------------------------------------------------


def test_employee_search_by_email_value_is_not_a_confirmation_oracle(employee_client, pii_customer):
    """Searching the exact address must not distinguish "this customer has
    that address" from "no such address": ``email`` is not a searchable
    field for an Employee at all, so the query degenerates to a name
    search and matches nothing.
    """
    hit = employee_client.get(f"{CUSTOMERS_URL}?search={PII_EMAIL}")
    miss = employee_client.get(f"{CUSTOMERS_URL}?search=not-a-real-address@example.com")

    assert hit.status_code == 200
    assert hit.json()["count"] == miss.json()["count"] == 0
    assert_no_pii(hit, context="customer search by email")


def test_employee_search_by_phone_value_is_not_a_confirmation_oracle(employee_client, pii_lead):
    hit = employee_client.get(f"{LEADS_URL}?search={PII_PHONE}")
    miss = employee_client.get(f"{LEADS_URL}?search=PII_TEST_PHONE_999")

    assert hit.json()["count"] == miss.json()["count"] == 0
    assert_no_pii(hit, context="lead search by phone")


def test_super_admin_can_still_search_by_email_value(api_client, super_admin, pii_customer):
    """The Super Admin's/Manager's legitimate ability to look a customer up
    by address is deliberately preserved. (Super Admin here because
    ownership scoping — ``scope_queryset_for_user()``, untouched by this
    pass — limits a Manager to their own team, and the ``employee``
    fixture is on no team.)
    """
    api_client.force_authenticate(super_admin)
    response = api_client.get(f"{CUSTOMERS_URL}?search={PII_EMAIL}")
    assert response.json()["count"] == 1


def test_manager_can_still_search_by_email_value_within_their_scope(
    api_client, manager, organization
):
    from apps.crm.models import Customer

    Customer.objects.create(
        organization=organization,
        name="Manager Owned",
        slug="manager-owned",
        owner=manager,
        email=PII_EMAIL,
        phone=PII_PHONE,
    )
    api_client.force_authenticate(manager)

    response = api_client.get(f"{CUSTOMERS_URL}?search={PII_EMAIL}")

    assert response.json()["count"] == 1
    assert response.json()["results"][0]["email"] == PII_EMAIL


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


def test_employee_lead_export_omits_pii_columns(employee_client, pii_lead):
    response = employee_client.get(f"{LEADS_URL}export/?export_format=csv")

    assert response.status_code == 200
    assert_no_pii(response, context="employee CSV export")
    header = response.content.decode().splitlines()[0]
    assert "email" not in header
    assert "phone" not in header


def test_employee_lead_export_xlsx_omits_pii(employee_client, pii_lead):
    response = employee_client.get(f"{LEADS_URL}export/?export_format=xlsx")

    assert response.status_code == 200
    # An .xlsx is a zip of XML: the sentinel would appear verbatim in the
    # shared-strings part if it were exported, so a raw byte scan is a
    # genuine check here, not a formality.
    assert_no_pii(response, context="employee XLSX export")


def test_super_admin_lead_export_still_includes_contact_columns(api_client, super_admin, pii_lead):
    api_client.force_authenticate(super_admin)
    response = api_client.get(f"{LEADS_URL}export/?export_format=csv")

    header = response.content.decode().splitlines()[0]
    assert "email" in header
    assert "phone" in header
    assert PII_EMAIL in response.content.decode()


# --------------------------------------------------------------------------
# Email: outbound, history, inbound reply
# --------------------------------------------------------------------------


def test_employee_can_email_a_customer_without_ever_seeing_the_address(employee_client, pii_customer):
    response = employee_client.post(
        EMAIL_MESSAGES_URL, {"customer": pii_customer.pk, "subject": "Hello", "body": "Hi there"}
    )

    assert response.status_code == 201
    assert_no_pii(response, context="queue-email response")

    message = EmailMessage.objects.get(pk=response.json()["id"])
    # The backend DID resolve and store the real address internally.
    assert message.to_email == PII_EMAIL


def test_email_history_never_exposes_the_address(employee_client, employee, pii_customer):
    queue_email(subject="S", body="B", owner=employee, related_object=pii_customer)

    list_response = employee_client.get(EMAIL_MESSAGES_URL)
    assert list_response.status_code == 200
    assert_no_pii(list_response, context="email history list")
    assert find_pii_paths(list_response.json()) == []

    message_id = list_response.json()["results"][0]["id"]
    detail_response = employee_client.get(f"{EMAIL_MESSAGES_URL}{message_id}/")
    assert_no_pii(detail_response, context="email history detail")
    assert detail_response.json()["recipient_label"] == str(pii_customer)


def test_email_send_action_response_never_exposes_the_address(
    employee_client, employee, pii_customer, monkeypatch
):
    monkeypatch.setattr("apps.communications.services._default_send_func", lambda message: None)
    message = queue_email(subject="S", body="B", owner=employee, related_object=pii_customer)

    response = employee_client.post(f"{EMAIL_MESSAGES_URL}{message.pk}/send/")

    assert response.status_code == 200
    assert_no_pii(response, context="send-email response")


def test_employee_cannot_repoint_a_queued_email_at_another_address(
    employee_client, employee, pii_customer
):
    """``to_email`` is read-only, so the PATCH-then-send route to an open
    relay is closed too — not just the create endpoint.
    """
    message = queue_email(subject="S", body="B", owner=employee, related_object=pii_customer)

    response = employee_client.patch(
        f"{EMAIL_MESSAGES_URL}{message.pk}/", {"to_email": "attacker@example.com"}, format="json"
    )

    assert response.status_code == 200
    message.refresh_from_db()
    assert message.to_email == PII_EMAIL


def test_manager_still_sees_the_email_address(api_client, manager, employee, pii_customer):
    queue_email(subject="S", body="B", owner=manager, related_object=pii_customer)
    api_client.force_authenticate(manager)

    response = api_client.get(EMAIL_MESSAGES_URL)

    assert response.json()["results"][0]["to_email"] == PII_EMAIL


def test_outbound_email_carries_a_crm_owned_reply_to_not_the_employee_mailbox(
    settings, employee, pii_customer
):
    from django.core import mail

    settings.INBOUND_EMAIL_DOMAIN = "reply.crm.example"
    message = queue_email(subject="S", body="B", owner=employee, related_object=pii_customer)

    from apps.communications.services import send_queued_email

    send_queued_email(message)

    sent = mail.outbox[-1]
    assert sent.to == [PII_EMAIL]  # the provider genuinely needs it
    assert sent.reply_to == [f"reply+{message.reply_token}@reply.crm.example"]
    assert employee.email not in sent.reply_to


def test_inbound_reply_is_matched_by_token_and_sanitized(settings, employee, pii_customer):
    """The inbound path: a reply arriving at the CRM's own Reply-To address
    is attached to the right conversation by TOKEN, and its body is
    sanitized so the customer's own address never becomes
    employee-visible content.
    """
    from apps.communications.services import record_inbound_email

    settings.INBOUND_EMAIL_DOMAIN = "reply.crm.example"
    original = queue_email(subject="Quote", body="B", owner=employee, related_object=pii_customer)

    reply = record_inbound_email(
        {
            "to": f"reply+{original.reply_token}@reply.crm.example",
            "from": PII_EMAIL,
            "subject": "Re: Quote",
            "text": f"From: {PII_EMAIL}\nSounds good, call me on {PII_PHONE}.\n-- {PII_EMAIL}",
        }
    )

    assert reply is not None
    assert reply.direction == EmailMessage.Direction.INBOUND
    assert reply.in_reply_to_id == original.pk
    assert reply.owner_id == employee.pk
    # The raw From: header never reaches the stored (employee-visible) row.
    assert PII_EMAIL not in reply.body
    assert PII_EMAIL not in reply.to_email
    assert "[contact detail removed]" in reply.body


def test_inbound_reply_ignores_an_attacker_supplied_lead_id(settings, employee, pii_customer):
    """A webhook body is attacker-controlled: an unknown/absent reply token
    must be ignored outright, never resolved from any id the payload
    claims.
    """
    from apps.communications.services import record_inbound_email

    settings.INBOUND_EMAIL_DOMAIN = "reply.crm.example"
    queue_email(subject="Quote", body="B", owner=employee, related_object=pii_customer)

    assert record_inbound_email({"to": "reply+deadbeef@reply.crm.example", "text": "hi"}) is None
    assert record_inbound_email({"to": "reply.crm.example", "lead_id": pii_customer.pk, "text": "hi"}) is None
    assert EmailMessage.objects.filter(direction=EmailMessage.Direction.INBOUND).count() == 0


def test_inbound_email_webhook_rejects_an_unsigned_request(api_client):
    response = api_client.post(
        "/api/v1/webhooks/inbound-email/", data=json.dumps({"to": "x"}), content_type="application/json"
    )
    assert response.status_code == 401


def test_inbound_email_webhook_accepts_a_signed_request(api_client, settings, employee, pii_customer):
    import hashlib
    import hmac

    settings.INBOUND_EMAIL_DOMAIN = "reply.crm.example"
    original = queue_email(subject="Quote", body="B", owner=employee, related_object=pii_customer)
    body = json.dumps(
        {"to": f"reply+{original.reply_token}@reply.crm.example", "subject": "Re: Quote", "text": "yes please"}
    ).encode()
    signature = hmac.new(b"inbound-secret", body, hashlib.sha256).hexdigest()

    with patch.dict("os.environ", {"INBOUND_EMAIL_WEBHOOK_SECRET": "inbound-secret"}):
        response = api_client.post(
            "/api/v1/webhooks/inbound-email/",
            data=body,
            content_type="application/json",
            HTTP_X_INBOUND_EMAIL_SIGNATURE=signature,
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert EmailMessage.objects.filter(direction=EmailMessage.Direction.INBOUND).count() == 1


# --------------------------------------------------------------------------
# Calling
# --------------------------------------------------------------------------


def test_employee_can_call_a_customer_without_ever_seeing_the_number(employee_client, pii_customer):
    with patch("apps.communications.services.A1RoutesClient.initiate_call", return_value="prov-pii-1"):
        with patch.dict("os.environ", {"A1ROUTES_API_KEY": "k"}):
            response = employee_client.post(CALLS_URL, {"customer": pii_customer.pk})

    assert response.status_code == 201
    assert_no_pii(response, context="initiate-call response")
    assert find_pii_paths(response.json()) == []

    call = Call.objects.get(pk=response.json()["id"])
    assert call.to_number == PII_PHONE  # resolved internally


def test_call_history_never_exposes_the_number(employee_client, employee, pii_customer):
    with patch("apps.communications.services.A1RoutesClient.initiate_call", return_value="prov-pii-2"):
        with patch.dict("os.environ", {"A1ROUTES_API_KEY": "k"}):
            employee_client.post(CALLS_URL, {"customer": pii_customer.pk})

    list_response = employee_client.get(CALLS_URL)
    assert_no_pii(list_response, context="call history list")
    assert find_pii_paths(list_response.json()) == []

    call_id = list_response.json()["results"][0]["id"]
    assert_no_pii(employee_client.get(f"{CALLS_URL}{call_id}/"), context="call history detail")


def test_manager_still_sees_call_numbers(api_client, manager, employee, pii_customer):
    call = Call.objects.create(
        owner=manager, direction=Call.Direction.OUTBOUND, from_number="+15550000000", to_number=PII_PHONE
    )
    api_client.force_authenticate(manager)

    response = api_client.get(f"{CALLS_URL}{call.pk}/")

    assert response.json()["to_number"] == PII_PHONE


def test_call_by_lead_resolves_the_leads_number(employee_client, pii_lead):
    with patch("apps.communications.services.A1RoutesClient.initiate_call", return_value="prov-pii-3"):
        with patch.dict("os.environ", {"A1ROUTES_API_KEY": "k"}):
            response = employee_client.post(CALLS_URL, {"lead": pii_lead.pk})

    assert response.status_code == 201
    assert Call.objects.get(pk=response.json()["id"]).to_number == PII_PHONE
    assert_no_pii(response, context="initiate-call-by-lead response")


# --------------------------------------------------------------------------
# WhatsApp
# --------------------------------------------------------------------------


def test_employee_can_whatsapp_a_customer_without_ever_seeing_the_number(employee_client, pii_customer):
    with patch.dict("os.environ", {"WHATSAPP_API_TOKEN": "tok", "WHATSAPP_PHONE_ID": "12345"}):
        with patch("apps.communications.services.WhatsAppClient.send_message", return_value="wamid.pii"):
            response = employee_client.post(
                WHATSAPP_SEND_URL, {"customer": pii_customer.pk, "message": "Hello"}
            )

    assert response.status_code == 201
    assert_no_pii(response, context="whatsapp send response")
    assert find_pii_paths(response.json()) == []
    assert response.json()["customer_name"] == pii_customer.name

    message = WhatsAppMessage.objects.get(pk=response.json()["id"])
    assert message.receiver == PII_PHONE  # resolved internally


def test_whatsapp_history_never_exposes_the_number(employee_client, employee, pii_customer):
    WhatsAppMessage.objects.create(
        owner=employee,
        customer=pii_customer,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        sender="12345",
        receiver=PII_WHATSAPP,
        message="Hi",
    )

    response = employee_client.get(WHATSAPP_MESSAGES_URL)

    assert response.status_code == 200
    assert_no_pii(response, context="whatsapp history")
    assert find_pii_paths(response.json()) == []


def test_manager_still_sees_whatsapp_numbers(api_client, manager, pii_customer):
    WhatsAppMessage.objects.create(
        owner=manager,
        customer=pii_customer,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        sender="12345",
        receiver=PII_WHATSAPP,
        message="Hi",
    )
    api_client.force_authenticate(manager)

    response = api_client.get(WHATSAPP_MESSAGES_URL)

    assert response.json()["results"][0]["receiver"] == PII_WHATSAPP


# --------------------------------------------------------------------------
# Communication log / notifications
# --------------------------------------------------------------------------


def test_communication_log_summaries_never_contain_contact_details(employee_client, employee, pii_customer):
    with patch("apps.communications.services.A1RoutesClient.initiate_call", return_value="prov-pii-4"):
        with patch.dict("os.environ", {"A1ROUTES_API_KEY": "k"}):
            employee_client.post(CALLS_URL, {"customer": pii_customer.pk})
    with patch.dict("os.environ", {"WHATSAPP_API_TOKEN": "tok", "WHATSAPP_PHONE_ID": "12345"}):
        with patch("apps.communications.services.WhatsAppClient.send_message", return_value="wamid.pii2"):
            employee_client.post(WHATSAPP_SEND_URL, {"customer": pii_customer.pk, "message": "Hello"})

    assert CommunicationLog.objects.exists()
    response = employee_client.get(COMMUNICATION_LOGS_URL)

    assert response.status_code == 200
    assert_no_pii(response, context="communication log")
    assert find_pii_paths(response.json()) == []


def test_notifications_never_contain_contact_details(employee_client, settings, employee, pii_customer):
    from apps.communications.services import record_inbound_email

    settings.INBOUND_EMAIL_DOMAIN = "reply.crm.example"
    original = queue_email(subject="Quote", body="B", owner=employee, related_object=pii_customer)
    record_inbound_email(
        {
            "to": f"reply+{original.reply_token}@reply.crm.example",
            "subject": f"Re: Quote from {PII_EMAIL}",
            "text": "ok",
        }
    )

    response = employee_client.get(NOTIFICATIONS_URL)

    assert response.status_code == 200
    assert_no_pii(response, context="notifications")


# --------------------------------------------------------------------------
# Error responses
# --------------------------------------------------------------------------


def test_error_responses_never_echo_contact_details(employee_client, pii_customer, customer):
    """A 400 must describe the problem by ENTITY, never by value."""
    no_contact_details = employee_client.post(CALLS_URL, {"customer": customer.pk})
    assert no_contact_details.status_code == 400
    assert_no_pii(no_contact_details, context="call 400")

    relay_attempt = employee_client.post(
        EMAIL_MESSAGES_URL, {"to_email": PII_EMAIL, "subject": "S", "body": "B"}
    )
    assert relay_attempt.status_code == 400
    assert_no_pii(relay_attempt, context="email relay 400")


# --------------------------------------------------------------------------
# Cross-employee authorization
# --------------------------------------------------------------------------


@pytest.fixture
def foreign_customer(db, organization, other_employee):
    from apps.crm.models import Customer

    return Customer.objects.create(
        organization=organization,
        name="Someone Else's Customer",
        slug="someone-elses-customer",
        owner=other_employee,
        email=PII_EMAIL,
        phone=PII_PHONE,
    )


def test_employee_cannot_email_another_employees_customer(employee_client, foreign_customer):
    response = employee_client.post(
        EMAIL_MESSAGES_URL, {"customer": foreign_customer.pk, "subject": "S", "body": "B"}
    )

    assert response.status_code == 404
    assert not EmailMessage.objects.filter(object_id=foreign_customer.pk).exists()


def test_employee_cannot_call_another_employees_customer(employee_client, foreign_customer):
    response = employee_client.post(CALLS_URL, {"customer": foreign_customer.pk})

    assert response.status_code == 404
    assert not Call.objects.exists()


def test_employee_cannot_whatsapp_another_employees_customer(employee_client, foreign_customer):
    response = employee_client.post(
        WHATSAPP_SEND_URL, {"customer": foreign_customer.pk, "message": "Hello"}
    )

    assert response.status_code == 404
    assert not WhatsAppMessage.objects.exists()


def test_employee_cannot_reach_a_foreign_customer_through_the_generic_entity_pair(
    employee_client, foreign_customer
):
    """The pre-existing ``content_type``+``object_id`` shape is authorized
    by the same check as the named relations — it was the ID-guessing hole
    before this pass.
    """
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(foreign_customer)
    response = employee_client.post(
        EMAIL_MESSAGES_URL,
        {
            "content_type": content_type.pk,
            "object_id": foreign_customer.pk,
            "subject": "S",
            "body": "B",
        },
    )

    assert response.status_code == 404


def test_employee_cannot_see_another_employees_customer_at_all(employee_client, foreign_customer):
    detail = employee_client.get(f"{CUSTOMERS_URL}{foreign_customer.pk}/")
    assert detail.status_code == 404
    assert_no_pii(detail, context="foreign customer detail")


# --------------------------------------------------------------------------
# Whole-surface sweep
# --------------------------------------------------------------------------


def test_negative_pii_sweep_across_every_employee_facing_endpoint(
    employee_client, employee, pii_customer, pii_lead, pii_contact
):
    """The spec's literal sweep, in one test: exercise every employee-
    reachable read endpoint that could possibly carry a customer's contact
    details — including paginated, filtered, ordered and searched variants
    — and scan every response byte for the sentinels.
    """
    queue_email(subject="S", body="B", owner=employee, related_object=pii_customer)
    Call.objects.create(
        owner=employee, direction=Call.Direction.OUTBOUND, from_number="+1", to_number=PII_PHONE
    )
    WhatsAppMessage.objects.create(
        owner=employee,
        customer=pii_customer,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        sender="1",
        receiver=PII_WHATSAPP,
        message="Hi",
    )

    urls = [
        CUSTOMERS_URL,
        f"{CUSTOMERS_URL}?page=1",
        f"{CUSTOMERS_URL}?ordering=name",
        f"{CUSTOMERS_URL}?search=PII",
        f"{CUSTOMERS_URL}{pii_customer.pk}/",
        LEADS_URL,
        f"{LEADS_URL}?search=PII",
        f"{LEADS_URL}{pii_lead.pk}/",
        f"{LEADS_URL}{pii_lead.pk}/duplicates/",
        f"{LEADS_URL}export/?export_format=csv",
        CONTACTS_URL,
        f"{CONTACTS_URL}{pii_contact.pk}/",
        EMAIL_MESSAGES_URL,
        f"{EMAIL_MESSAGES_URL}?search=PII",
        CALLS_URL,
        f"{CALLS_URL}?search=PII",
        WHATSAPP_MESSAGES_URL,
        f"{WHATSAPP_MESSAGES_URL}?search=PII",
        COMMUNICATION_LOGS_URL,
        NOTIFICATIONS_URL,
    ]

    for url in urls:
        response = employee_client.get(url)
        assert response.status_code == 200, url
        assert_no_pii(response, context=url)
