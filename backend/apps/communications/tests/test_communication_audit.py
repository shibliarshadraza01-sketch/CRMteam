"""Super-Admin communication audit-trail tests.

A sibling of ``test_pii_privacy.py``, not an extension of it: that module
asserts the EMPLOYEE boundary (no customer contact detail ever crosses it);
this one asserts the SUPER ADMIN capability layered on top (the complete,
immutable, cross-channel communication history is retrievable — and
retrievable ONLY — by a Super Admin, server-side).

The module is organised as the spec's own 16-point audit-testing
checklist, one section per point, so a reader can map a requirement to the
test that proves it. Several points were already covered by
``test_pii_privacy.py`` before this pass; those are re-asserted here from
the AUDIT angle (was the touchpoint RECORDED?) rather than duplicated from
the privacy angle (was the value HIDDEN?), because a record that exists but
is invisible and a value that is hidden but unrecorded are two different
failures.

Nothing here is allowed to relax the employee boundary — several tests
deliberately assert that the audit surface is NOT a way around it.
"""
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest

from apps.communications.models import Call, CommunicationLog, EmailMessage, WhatsAppMessage
from apps.communications.services import queue_email, send_queued_email

pytestmark = pytest.mark.django_db

AUDIT_EMAIL = "AUDIT_TEST_EMAIL_777@example.com"
AUDIT_PHONE = "AUDIT_TEST_PHONE_777"

EMAIL_MESSAGES_URL = "/api/v1/communications/email-messages/"
CALLS_URL = "/api/v1/communications/calls/"
WHATSAPP_SEND_URL = "/api/v1/communications/whatsapp/send/"
WHATSAPP_MESSAGES_URL = "/api/v1/communications/whatsapp/messages/"
COMMUNICATION_LOGS_URL = "/api/v1/communications/communication-logs/"

A1ROUTES_WEBHOOK_URL = "/api/v1/webhooks/a1routes/"
WHATSAPP_WEBHOOK_URL = "/api/v1/webhooks/whatsapp/"
INBOUND_EMAIL_WEBHOOK_URL = "/api/v1/webhooks/inbound-email/"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def audit_customer(db, organization, employee):
    from apps.crm.models import Customer

    return Customer.objects.create(
        organization=organization,
        name="Audit Sentinel Customer",
        slug="audit-sentinel-customer",
        owner=employee,
        email=AUDIT_EMAIL,
        phone=AUDIT_PHONE,
    )


@pytest.fixture
def audit_lead(db, employee):
    from apps.crm.models import Lead

    return Lead.objects.create(
        company_name="Audit Sentinel Co",
        contact_name="Audit Sentinel Contact",
        owner=employee,
        email=AUDIT_EMAIL,
        phone=AUDIT_PHONE,
    )


@pytest.fixture
def employee_client(api_client, employee):
    api_client.force_authenticate(employee)
    return api_client


@pytest.fixture
def super_admin_client(super_admin):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(super_admin)
    return client


def a1routes_post(client, payload, secret="a1-secret"):
    body = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    with patch.dict("os.environ", {"A1ROUTES_WEBHOOK_SECRET": secret}):
        return client.post(
            A1ROUTES_WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_A1ROUTES_SIGNATURE=signature,
        )


def whatsapp_post(client, payload, secret="wa-secret"):
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    with patch.dict("os.environ", {"WHATSAPP_APP_SECRET": secret}):
        return client.post(
            WHATSAPP_WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )


def place_call(client, customer, provider_call_id):
    with patch("apps.communications.services.A1RoutesClient.initiate_call", return_value=provider_call_id):
        with patch.dict("os.environ", {"A1ROUTES_API_KEY": "k"}):
            return client.post(CALLS_URL, {"customer": customer.pk})


def send_whatsapp(client, customer, text, provider_message_id):
    with patch.dict("os.environ", {"WHATSAPP_API_TOKEN": "tok", "WHATSAPP_PHONE_ID": "12345"}):
        with patch("apps.communications.services.WhatsAppClient.send_message", return_value=provider_message_id):
            return client.post(WHATSAPP_SEND_URL, {"customer": customer.pk, "message": text})


# --------------------------------------------------------------------------
# (1) An employee can send an email
# (2) The email is recorded
# --------------------------------------------------------------------------


def test_employee_can_send_an_email_and_it_is_recorded(employee_client, employee, audit_customer):
    queue_response = employee_client.post(
        EMAIL_MESSAGES_URL, {"customer": audit_customer.pk, "subject": "Audit hello", "body": "Body"}
    )
    assert queue_response.status_code == 201
    message_id = queue_response.json()["id"]

    send_response = employee_client.post(f"{EMAIL_MESSAGES_URL}{message_id}/send/")
    assert send_response.status_code == 200

    message = EmailMessage.objects.get(pk=message_id)
    assert message.status == EmailMessage.Status.SENT
    assert message.owner_id == employee.pk
    assert message.object_id == audit_customer.pk

    log = CommunicationLog.objects.filter(channel=CommunicationLog.Channel.EMAIL).latest("occurred_at")
    assert log.actor_id == employee.pk
    assert log.object_id == audit_customer.pk
    assert AUDIT_EMAIL not in log.summary


# --------------------------------------------------------------------------
# (3) A customer reply is recorded
# --------------------------------------------------------------------------


def test_customer_email_reply_is_recorded(api_client, settings, employee, audit_customer):
    settings.INBOUND_EMAIL_DOMAIN = "reply.crm.example"
    original = queue_email(subject="Audit quote", body="B", owner=employee, related_object=audit_customer)

    body = json.dumps(
        {
            "to": f"reply+{original.reply_token}@reply.crm.example",
            "subject": "Re: Audit quote",
            "text": "Yes please",
        }
    ).encode()
    signature = hmac.new(b"inbound-secret", body, hashlib.sha256).hexdigest()
    with patch.dict("os.environ", {"INBOUND_EMAIL_WEBHOOK_SECRET": "inbound-secret"}):
        response = api_client.post(
            INBOUND_EMAIL_WEBHOOK_URL,
            data=body,
            content_type="application/json",
            HTTP_X_INBOUND_EMAIL_SIGNATURE=signature,
        )

    assert response.status_code == 200
    reply = EmailMessage.objects.get(direction=EmailMessage.Direction.INBOUND)
    assert reply.in_reply_to_id == original.pk
    assert reply.object_id == audit_customer.pk
    assert CommunicationLog.objects.filter(
        channel=CommunicationLog.Channel.EMAIL, summary__icontains="reply received"
    ).exists()


# --------------------------------------------------------------------------
# (4) The employee can see the conversation
# (5) The employee cannot see the customer's raw email
# --------------------------------------------------------------------------


def test_employee_sees_the_conversation_but_never_the_raw_address(employee_client, employee, audit_customer):
    employee_client.post(
        EMAIL_MESSAGES_URL, {"customer": audit_customer.pk, "subject": "Audit thread", "body": "Body"}
    )

    response = employee_client.get(EMAIL_MESSAGES_URL)

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    row = payload["results"][0]
    assert row["subject"] == "Audit thread"
    assert row["recipient_label"] == str(audit_customer)
    # The whole point: the conversation is visible, the address is not.
    assert "to_email" not in row
    assert AUDIT_EMAIL not in response.content.decode()


# --------------------------------------------------------------------------
# (6) An employee can initiate a call
# (7) The call is recorded
# --------------------------------------------------------------------------


def test_employee_can_initiate_a_call_and_it_is_recorded(employee_client, employee, audit_customer):
    response = place_call(employee_client, audit_customer, "prov-audit-1")

    assert response.status_code == 201
    call = Call.objects.get(pk=response.json()["id"])
    assert call.owner_id == employee.pk
    assert call.object_id == audit_customer.pk
    assert call.provider_call_id == "prov-audit-1"
    assert call.direction == Call.Direction.OUTBOUND

    log = CommunicationLog.objects.get(channel=CommunicationLog.Channel.CALL)
    assert log.actor_id == employee.pk
    assert AUDIT_PHONE not in log.summary


# --------------------------------------------------------------------------
# (8) WhatsApp messages are recorded
# --------------------------------------------------------------------------


def test_outbound_whatsapp_message_is_recorded(employee_client, employee, audit_customer):
    response = send_whatsapp(employee_client, audit_customer, "Audit hi", "wamid.audit1")

    assert response.status_code == 201
    message = WhatsAppMessage.objects.get(pk=response.json()["id"])
    assert message.owner_id == employee.pk
    assert message.customer_id == audit_customer.pk
    assert message.provider_message_id == "wamid.audit1"
    assert message.status == WhatsAppMessage.Status.SENT

    assert CommunicationLog.objects.filter(
        channel=CommunicationLog.Channel.WHATSAPP, actor=employee, summary__icontains="sent"
    ).exists()


# --------------------------------------------------------------------------
# (9) WhatsApp replies are recorded
# --------------------------------------------------------------------------


def test_inbound_whatsapp_reply_is_recorded_and_attributed(api_client, employee, audit_customer):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "12345"},
                            "messages": [
                                {
                                    "id": "wamid.inbound1",
                                    "from": AUDIT_PHONE,
                                    "type": "text",
                                    "text": {"body": "Customer replied"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }

    response = whatsapp_post(api_client, payload)

    assert response.status_code == 200
    reply = WhatsAppMessage.objects.get(direction=WhatsAppMessage.Direction.INBOUND)
    assert reply.message == "Customer replied"
    assert reply.customer_id == audit_customer.pk
    assert reply.owner_id == employee.pk  # the customer's owner, resolved server-side
    assert reply.provider_message_id == "wamid.inbound1"
    assert CommunicationLog.objects.filter(
        channel=CommunicationLog.Channel.WHATSAPP, summary__icontains="reply received"
    ).exists()


def test_inbound_whatsapp_reply_is_idempotent_across_provider_retries(api_client, audit_customer):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "12345"},
                            "messages": [
                                {"id": "wamid.retry", "from": AUDIT_PHONE, "type": "text", "text": {"body": "Hi"}}
                            ],
                        }
                    }
                ]
            }
        ]
    }

    whatsapp_post(api_client, payload)
    whatsapp_post(api_client, payload)

    assert WhatsAppMessage.objects.filter(direction=WhatsAppMessage.Direction.INBOUND).count() == 1


def test_inbound_whatsapp_from_an_unknown_number_is_still_recorded_unattached(api_client):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"id": "wamid.unknown", "from": "+1999000111", "type": "text", "text": {"body": "?"}}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    whatsapp_post(api_client, payload)

    reply = WhatsAppMessage.objects.get(direction=WhatsAppMessage.Direction.INBOUND)
    # Never guessed at a customer — the touchpoint is kept, the attribution isn't invented.
    assert reply.customer_id is None
    assert reply.owner_id is None


# --------------------------------------------------------------------------
# (10) A Super Admin can retrieve the complete communication history
# --------------------------------------------------------------------------


def test_super_admin_retrieves_the_complete_cross_channel_history(
    employee_client, super_admin_client, employee, audit_customer
):
    employee_client.post(
        EMAIL_MESSAGES_URL, {"customer": audit_customer.pk, "subject": "Audit mail", "body": "B"}
    )
    place_call(employee_client, audit_customer, "prov-audit-10")
    send_whatsapp(employee_client, audit_customer, "Audit wa", "wamid.audit10")

    emails = super_admin_client.get(EMAIL_MESSAGES_URL)
    calls = super_admin_client.get(CALLS_URL)
    whatsapp = super_admin_client.get(WHATSAPP_MESSAGES_URL)
    logs = super_admin_client.get(COMMUNICATION_LOGS_URL)

    assert emails.json()["count"] == 1
    assert calls.json()["count"] == 1
    assert whatsapp.json()["count"] == 1
    assert logs.json()["count"] >= 2

    # ...and, unlike the employee, WITH the contact detail the audit
    # interface is explicitly authorized to show.
    assert emails.json()["results"][0]["to_email"] == AUDIT_EMAIL
    assert calls.json()["results"][0]["to_number"] == AUDIT_PHONE
    assert whatsapp.json()["results"][0]["receiver"] == AUDIT_PHONE

    # Every audit row names the employee who performed the action.
    assert emails.json()["results"][0]["owner"] == employee.pk
    assert calls.json()["results"][0]["owner"] == employee.pk
    assert whatsapp.json()["results"][0]["owner"] == employee.pk


def test_super_admin_sees_every_employees_history_not_just_their_own(
    api_client, super_admin_client, employee, other_employee, audit_customer
):
    EmailMessage.objects.create(owner=employee, to_email=AUDIT_EMAIL, subject="A", body="A")
    EmailMessage.objects.create(owner=other_employee, to_email=AUDIT_EMAIL, subject="B", body="B")

    response = super_admin_client.get(EMAIL_MESSAGES_URL)

    assert response.json()["count"] == 2


def test_super_admin_can_filter_the_audit_trail_by_employee_channel_direction_status_and_date(
    super_admin_client, employee, other_employee, audit_customer
):
    from datetime import timedelta
    from urllib.parse import quote

    from django.utils import timezone

    mine = EmailMessage.objects.create(
        owner=employee,
        to_email=AUDIT_EMAIL,
        subject="Mine",
        body="B",
        status=EmailMessage.Status.SENT,
        direction=EmailMessage.Direction.OUTBOUND,
    )
    EmailMessage.objects.create(
        owner=other_employee, to_email=AUDIT_EMAIL, subject="Theirs", body="B", status=EmailMessage.Status.FAILED
    )

    by_employee = super_admin_client.get(f"{EMAIL_MESSAGES_URL}?owner={employee.pk}")
    assert [row["id"] for row in by_employee.json()["results"]] == [mine.pk]

    by_status = super_admin_client.get(f"{EMAIL_MESSAGES_URL}?status=SENT")
    assert [row["id"] for row in by_status.json()["results"]] == [mine.pk]

    by_direction = super_admin_client.get(f"{EMAIL_MESSAGES_URL}?direction=OUTBOUND")
    assert by_direction.json()["count"] == 2  # both default to OUTBOUND

    # quote() matters: an ISO-8601 offset ("+00:00") decodes as a space
    # in an un-encoded query string, which django-filter then rejects.
    window_start = quote((timezone.now() - timedelta(hours=1)).isoformat())
    in_window = super_admin_client.get(f"{EMAIL_MESSAGES_URL}?created_from={window_start}")
    assert in_window.status_code == 200, in_window.content
    assert in_window.json()["count"] == 2

    window_end = quote((timezone.now() - timedelta(days=2)).isoformat())
    out_of_window = super_admin_client.get(f"{EMAIL_MESSAGES_URL}?created_to={window_end}")
    assert out_of_window.json()["count"] == 0

    by_channel = super_admin_client.get(f"{COMMUNICATION_LOGS_URL}?channel=CALL")
    assert by_channel.status_code == 200


def test_super_admin_can_pull_one_leads_whole_thread_across_channels(
    employee_client, super_admin_client, audit_customer
):
    """The "complete conversation thread" requirement, exercised the way
    the Super Admin audit UI actually assembles it: per-channel list
    endpoints narrowed to one entity, merged client-side by timestamp.
    """
    from django.contrib.contenttypes.models import ContentType

    content_type = ContentType.objects.get_for_model(audit_customer).pk

    employee_client.post(
        EMAIL_MESSAGES_URL, {"customer": audit_customer.pk, "subject": "Thread mail", "body": "B"}
    )
    place_call(employee_client, audit_customer, "prov-thread")
    send_whatsapp(employee_client, audit_customer, "Thread wa", "wamid.thread")

    entity_query = f"?content_type={content_type}&object_id={audit_customer.pk}"
    emails = super_admin_client.get(f"{EMAIL_MESSAGES_URL}{entity_query}").json()["results"]
    calls = super_admin_client.get(f"{CALLS_URL}{entity_query}").json()["results"]
    whatsapp = super_admin_client.get(
        f"{WHATSAPP_MESSAGES_URL}?customer={audit_customer.pk}"
    ).json()["results"]

    thread = sorted(
        [("EMAIL", row["created_at"]) for row in emails]
        + [("CALL", row["created_at"]) for row in calls]
        + [("WHATSAPP", row["created_at"]) for row in whatsapp],
        key=lambda item: item[1],
    )

    assert {channel for channel, _ in thread} == {"EMAIL", "CALL", "WHATSAPP"}


# --------------------------------------------------------------------------
# (11) An employee cannot access Super Admin audit data
# --------------------------------------------------------------------------


def test_employee_cannot_read_another_employees_communication_records(
    employee_client, other_employee, audit_customer
):
    """There is no separate "audit endpoint" to 403 on — by design (see the
    report): the SAME endpoints are scoped server-side by
    ``scope_queryset_for_user()``, so the privileged data an audit reader
    sees simply does not exist in an Employee's queryset. This asserts the
    property that actually matters: an Employee cannot reach it, by list or
    by direct id, and cannot widen their own scope with a query parameter.
    """
    foreign_email = EmailMessage.objects.create(
        owner=other_employee, to_email=AUDIT_EMAIL, subject="Not yours", body="B"
    )
    foreign_call = Call.objects.create(
        owner=other_employee, direction=Call.Direction.OUTBOUND, from_number="+1", to_number=AUDIT_PHONE
    )
    foreign_wa = WhatsAppMessage.objects.create(
        owner=other_employee, direction=WhatsAppMessage.Direction.OUTBOUND, sender="1", receiver=AUDIT_PHONE, message="x"
    )
    foreign_log = CommunicationLog.objects.create(
        channel=CommunicationLog.Channel.EMAIL, summary="Not yours", actor=other_employee
    )

    assert employee_client.get(EMAIL_MESSAGES_URL).json()["count"] == 0
    assert employee_client.get(CALLS_URL).json()["count"] == 0
    assert employee_client.get(WHATSAPP_MESSAGES_URL).json()["count"] == 0
    assert employee_client.get(COMMUNICATION_LOGS_URL).json()["count"] == 0

    assert employee_client.get(f"{EMAIL_MESSAGES_URL}{foreign_email.pk}/").status_code == 404
    assert employee_client.get(f"{CALLS_URL}{foreign_call.pk}/").status_code == 404
    assert employee_client.get(f"{WHATSAPP_MESSAGES_URL}{foreign_wa.pk}/").status_code == 404
    assert employee_client.get(f"{COMMUNICATION_LOGS_URL}{foreign_log.pk}/").status_code == 404


def test_a_client_supplied_owner_filter_cannot_widen_an_employees_scope(
    employee_client, other_employee, audit_customer
):
    """The spec's "never trust a client-supplied role/query-param for
    authorization" rule: filtering runs AFTER scoping, so naming someone
    else's id narrows, it never widens.
    """
    EmailMessage.objects.create(owner=other_employee, to_email=AUDIT_EMAIL, subject="Not yours", body="B")

    response = employee_client.get(f"{EMAIL_MESSAGES_URL}?owner={other_employee.pk}")

    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_an_employee_claiming_super_admin_in_the_request_gains_nothing(
    employee_client, other_employee
):
    EmailMessage.objects.create(owner=other_employee, to_email=AUDIT_EMAIL, subject="Not yours", body="B")

    response = employee_client.get(f"{EMAIL_MESSAGES_URL}?role=superadmin&is_super_admin=true")

    assert response.json()["count"] == 0


def test_unauthenticated_access_to_the_audit_surface_is_rejected(api_client):
    for url in (EMAIL_MESSAGES_URL, CALLS_URL, WHATSAPP_MESSAGES_URL, COMMUNICATION_LOGS_URL):
        assert api_client.get(url).status_code in (401, 403), url


# --------------------------------------------------------------------------
# (12) An employee cannot modify audit records
# --------------------------------------------------------------------------


def test_communication_log_has_no_write_verb_for_any_role(employee_client, super_admin_client, employee):
    log = CommunicationLog.objects.create(
        channel=CommunicationLog.Channel.EMAIL, summary="Immutable", actor=employee
    )

    for client in (employee_client, super_admin_client):
        assert client.post(COMMUNICATION_LOGS_URL, {"channel": "EMAIL", "summary": "forged"}).status_code == 405
        assert client.patch(f"{COMMUNICATION_LOGS_URL}{log.pk}/", {"summary": "rewritten"}).status_code == 405
        assert client.put(f"{COMMUNICATION_LOGS_URL}{log.pk}/", {"summary": "rewritten"}).status_code == 405
        assert client.delete(f"{COMMUNICATION_LOGS_URL}{log.pk}/").status_code == 405

    log.refresh_from_db()
    assert log.summary == "Immutable"


def test_employee_cannot_rewrite_call_or_whatsapp_attribution_status_or_duration(
    employee_client, employee, audit_customer
):
    call = Call.objects.create(
        owner=employee,
        direction=Call.Direction.OUTBOUND,
        from_number="+1",
        to_number=AUDIT_PHONE,
        status=Call.Status.COMPLETED,
        duration_seconds=42,
    )
    message = WhatsAppMessage.objects.create(
        owner=employee,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        sender="1",
        receiver=AUDIT_PHONE,
        message="x",
        status=WhatsAppMessage.Status.DELIVERED,
    )

    # PATCH isn't even routed on these two viewsets (GET/POST only).
    assert employee_client.patch(f"{CALLS_URL}{call.pk}/", {"status": "FAILED", "duration_seconds": 1}).status_code == 405
    assert employee_client.patch(f"{WHATSAPP_MESSAGES_URL}{message.pk}/", {"status": "FAILED"}).status_code == 405

    call.refresh_from_db()
    message.refresh_from_db()
    assert call.status == Call.Status.COMPLETED
    assert call.duration_seconds == 42
    assert message.status == WhatsAppMessage.Status.DELIVERED


def test_employee_cannot_rewrite_a_sent_emails_recorded_content_or_timestamps(employee_client, employee):
    message = EmailMessage.objects.create(
        owner=employee, to_email=AUDIT_EMAIL, subject="Recorded", body="Recorded body",
        status=EmailMessage.Status.SENT,
    )

    response = employee_client.patch(
        f"{EMAIL_MESSAGES_URL}{message.pk}/",
        {"subject": "Rewritten", "body": "Rewritten", "status": "QUEUED"},
    )

    message.refresh_from_db()
    assert response.status_code in (200, 400)
    assert message.subject == "Recorded"
    assert message.body == "Recorded body"
    assert message.status == EmailMessage.Status.SENT


# --------------------------------------------------------------------------
# (13) Records survive an application restart (i.e. are DB-persisted)
# --------------------------------------------------------------------------


def test_audit_records_are_database_rows_not_process_state(employee_client, employee, audit_customer):
    """A restart is simulated the only way it can be inside one test
    process: throw away every in-memory reference and every ORM cache, then
    re-read through a fresh queryset and a brand-new API client. Anything
    held in module state or a request-lifetime cache would vanish; a real
    table row does not.
    """
    from django.core.cache import cache
    from django.db import connection
    from rest_framework.test import APIClient

    employee_client.post(
        EMAIL_MESSAGES_URL, {"customer": audit_customer.pk, "subject": "Persisted", "body": "B"}
    )
    place_call(employee_client, audit_customer, "prov-persist")
    send_whatsapp(employee_client, audit_customer, "Persisted", "wamid.persist")

    cache.clear()

    # Straight to the database, bypassing every ORM instance already built.
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM communications_emailmessage")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM communications_call")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM communications_whatsappmessage")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT COUNT(*) FROM communications_communicationlog")
        assert cursor.fetchone()[0] >= 2

    fresh_client = APIClient()
    fresh_client.force_authenticate(employee)
    assert fresh_client.get(EMAIL_MESSAGES_URL).json()["count"] == 1
    assert fresh_client.get(CALLS_URL).json()["count"] == 1
    assert fresh_client.get(WHATSAPP_MESSAGES_URL).json()["count"] == 1


def test_history_survives_lead_reassignment_to_another_employee(
    super_admin_client, employee, other_employee, audit_customer
):
    """Reassignment must not orphan or hide history from the audit trail —
    the Super Admin's view is unscoped, so it keeps every row regardless of
    who currently owns the customer.
    """
    EmailMessage.objects.create(
        owner=employee, to_email=AUDIT_EMAIL, subject="Before reassignment", body="B"
    )

    audit_customer.owner = other_employee
    audit_customer.save(update_fields=["owner", "updated_at"])

    response = super_admin_client.get(EMAIL_MESSAGES_URL)

    assert response.json()["count"] == 1
    assert response.json()["results"][0]["owner"] == employee.pk


# --------------------------------------------------------------------------
# (14) Records are associated with BOTH the lead and the employee
# --------------------------------------------------------------------------


def test_every_channel_associates_the_record_with_the_lead_and_the_employee(
    employee_client, employee, audit_lead, audit_customer
):
    from django.contrib.contenttypes.models import ContentType

    employee_client.post(EMAIL_MESSAGES_URL, {"lead": audit_lead.pk, "subject": "Lead mail", "body": "B"})
    with patch("apps.communications.services.A1RoutesClient.initiate_call", return_value="prov-lead"):
        with patch.dict("os.environ", {"A1ROUTES_API_KEY": "k"}):
            employee_client.post(CALLS_URL, {"lead": audit_lead.pk})
    send_whatsapp(employee_client, audit_customer, "Customer wa", "wamid.assoc")

    lead_ct = ContentType.objects.get_for_model(audit_lead)

    email = EmailMessage.objects.get(subject="Lead mail")
    assert (email.content_type_id, email.object_id, email.owner_id) == (lead_ct.pk, audit_lead.pk, employee.pk)

    call = Call.objects.get(provider_call_id="prov-lead")
    assert (call.content_type_id, call.object_id, call.owner_id) == (lead_ct.pk, audit_lead.pk, employee.pk)

    wa = WhatsAppMessage.objects.get(provider_message_id="wamid.assoc")
    assert (wa.customer_id, wa.owner_id) == (audit_customer.pk, employee.pk)


# --------------------------------------------------------------------------
# (15) Failed communications are recorded too
# --------------------------------------------------------------------------


def test_a_failed_email_send_is_recorded_with_its_failure_reason(employee, audit_customer):
    message = queue_email(subject="Will fail", body="B", owner=employee, related_object=audit_customer)

    def explode(_message):
        raise RuntimeError("SMTP is down")

    send_queued_email(message, send_func=explode)

    message.refresh_from_db()
    assert message.status == EmailMessage.Status.FAILED
    assert "SMTP is down" in message.error_message
    assert CommunicationLog.objects.filter(
        channel=CommunicationLog.Channel.EMAIL, summary__icontains="failed"
    ).exists()


def test_a_failed_call_attempt_is_recorded(employee_client, employee, audit_customer):
    from apps.communications.providers.a1routes import A1RoutesError

    with patch(
        "apps.communications.services.A1RoutesClient.initiate_call", side_effect=A1RoutesError("trunk unreachable")
    ):
        with patch.dict("os.environ", {"A1ROUTES_API_KEY": "k"}):
            response = employee_client.post(CALLS_URL, {"customer": audit_customer.pk})

    assert response.status_code == 201  # the record of the attempt IS the response
    call = Call.objects.get(pk=response.json()["id"])
    assert call.status == Call.Status.FAILED
    assert "trunk unreachable" in call.error_message
    assert call.owner_id == employee.pk


def test_a_failed_whatsapp_send_is_recorded(employee_client, employee, audit_customer):
    from apps.communications.providers.whatsapp import WhatsAppError

    with patch.dict("os.environ", {"WHATSAPP_API_TOKEN": "tok", "WHATSAPP_PHONE_ID": "12345"}):
        with patch(
            "apps.communications.services.WhatsAppClient.send_message", side_effect=WhatsAppError("rejected")
        ):
            response = employee_client.post(
                WHATSAPP_SEND_URL, {"customer": audit_customer.pk, "message": "Hi"}
            )

    assert response.status_code == 201
    message = WhatsAppMessage.objects.get(pk=response.json()["id"])
    assert message.status == WhatsAppMessage.Status.FAILED
    assert "rejected" in message.error_message


# --------------------------------------------------------------------------
# (16) Provider webhook events are reflected in the audit trail
# --------------------------------------------------------------------------


def test_call_status_transitions_from_the_provider_become_audit_events(
    api_client, employee_client, employee, audit_customer
):
    place_call(employee_client, audit_customer, "prov-webhook-1")
    before = CommunicationLog.objects.filter(channel=CommunicationLog.Channel.CALL).count()

    assert a1routes_post(api_client, {"call_id": "prov-webhook-1", "status": "in-progress"}).status_code == 200
    assert a1routes_post(
        api_client, {"call_id": "prov-webhook-1", "status": "completed", "duration_seconds": 137}
    ).status_code == 200

    call = Call.objects.get(provider_call_id="prov-webhook-1")
    assert call.status == Call.Status.COMPLETED
    assert call.duration_seconds == 137
    assert call.ended_at is not None

    logs = CommunicationLog.objects.filter(channel=CommunicationLog.Channel.CALL).order_by("occurred_at")
    assert logs.count() == before + 2
    summaries = [log.summary for log in logs]
    assert any("connected" in summary for summary in summaries)
    assert any("completed" in summary for summary in summaries)
    assert all(log.actor_id == employee.pk for log in logs)
    assert all(AUDIT_PHONE not in log.summary for log in logs)


def test_a_replayed_call_webhook_does_not_duplicate_the_audit_event(
    api_client, employee_client, audit_customer
):
    place_call(employee_client, audit_customer, "prov-webhook-replay")
    a1routes_post(api_client, {"call_id": "prov-webhook-replay", "status": "completed"})
    count_after_first = CommunicationLog.objects.filter(channel=CommunicationLog.Channel.CALL).count()

    a1routes_post(api_client, {"call_id": "prov-webhook-replay", "status": "completed"})

    assert CommunicationLog.objects.filter(channel=CommunicationLog.Channel.CALL).count() == count_after_first


def test_a_failed_call_reported_by_the_provider_becomes_an_audit_event(
    api_client, employee_client, audit_customer
):
    place_call(employee_client, audit_customer, "prov-webhook-fail")

    a1routes_post(api_client, {"call_id": "prov-webhook-fail", "status": "no-answer"})

    assert Call.objects.get(provider_call_id="prov-webhook-fail").status == Call.Status.NO_ANSWER
    assert CommunicationLog.objects.filter(
        channel=CommunicationLog.Channel.CALL, summary__icontains="not answered"
    ).exists()


def test_whatsapp_delivery_and_read_receipts_become_audit_events(
    api_client, employee_client, employee, audit_customer
):
    send_whatsapp(employee_client, audit_customer, "Receipt test", "wamid.receipts")
    before = CommunicationLog.objects.filter(channel=CommunicationLog.Channel.WHATSAPP).count()

    for provider_status in ("delivered", "read"):
        payload = {
            "entry": [
                {"changes": [{"value": {"statuses": [{"id": "wamid.receipts", "status": provider_status}]}}]}
            ]
        }
        assert whatsapp_post(api_client, payload).status_code == 200

    message = WhatsAppMessage.objects.get(provider_message_id="wamid.receipts")
    assert message.status == WhatsAppMessage.Status.READ

    logs = CommunicationLog.objects.filter(channel=CommunicationLog.Channel.WHATSAPP).order_by("occurred_at")
    assert logs.count() == before + 2
    summaries = [log.summary for log in logs]
    assert any("delivered" in summary for summary in summaries)
    assert any("read" in summary for summary in summaries)
    assert all(log.actor_id == employee.pk for log in logs)


def test_whatsapp_failure_receipt_becomes_an_audit_event(api_client, employee_client, audit_customer):
    send_whatsapp(employee_client, audit_customer, "Will fail", "wamid.failed")

    payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.failed", "status": "failed"}]}}]}]}
    whatsapp_post(api_client, payload)

    assert WhatsAppMessage.objects.get(provider_message_id="wamid.failed").status == WhatsAppMessage.Status.FAILED
    assert CommunicationLog.objects.filter(
        channel=CommunicationLog.Channel.WHATSAPP, summary__icontains="failed"
    ).exists()


def test_an_unsigned_provider_webhook_cannot_write_to_the_audit_trail(api_client, employee_client, audit_customer):
    place_call(employee_client, audit_customer, "prov-unsigned")
    before = CommunicationLog.objects.count()

    response = api_client.post(
        A1ROUTES_WEBHOOK_URL,
        data=json.dumps({"call_id": "prov-unsigned", "status": "completed"}),
        content_type="application/json",
    )

    assert response.status_code == 401
    assert CommunicationLog.objects.count() == before
    assert Call.objects.get(provider_call_id="prov-unsigned").status == Call.Status.RINGING


# --------------------------------------------------------------------------
# Cross-cutting: the audit surface must never become a PII backdoor
# --------------------------------------------------------------------------


def test_the_webhook_generated_audit_events_are_pii_free_for_an_employee(
    api_client, employee_client, audit_customer
):
    place_call(employee_client, audit_customer, "prov-pii-webhook")
    a1routes_post(api_client, {"call_id": "prov-pii-webhook", "status": "completed", "duration_seconds": 9})
    send_whatsapp(employee_client, audit_customer, "Hi", "wamid.piiwebhook")
    whatsapp_post(
        api_client,
        {"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.piiwebhook", "status": "read"}]}}]}]},
    )

    body = employee_client.get(COMMUNICATION_LOGS_URL).content.decode()

    assert AUDIT_PHONE not in body
    assert AUDIT_EMAIL not in body


def test_an_inbound_whatsapp_reply_never_leaks_the_number_to_an_employee(
    api_client, employee_client, audit_customer
):
    whatsapp_post(
        api_client,
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "12345"},
                                "messages": [
                                    {"id": "wamid.pii-in", "from": AUDIT_PHONE, "type": "text", "text": {"body": "Hi"}}
                                ],
                            }
                        }
                    ]
                }
            ]
        },
    )

    response = employee_client.get(WHATSAPP_MESSAGES_URL)

    assert response.json()["count"] == 1
    assert AUDIT_PHONE not in response.content.decode()
    assert "sender" not in response.json()["results"][0]
