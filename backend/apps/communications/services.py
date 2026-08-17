"""CP15: reusable service functions for the communications domain.

Following the CP9-CP14 pattern: narrow, single-purpose, independently
testable functions for operations with real behavior beyond a single ORM
call.

Ownership scoping is NOT reimplemented — CP10's `managed_user_ids()`/
`scope_queryset_for_user()` are imported directly from `apps.crm.services`,
exactly as every checkpoint since CP12 has done, per this project's
standing "reuse existing infrastructure, do not duplicate logic" rule.
"""
import logging
import re
import secrets

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import EmailMessage as DjangoEmailMessage
from django.utils import timezone

from apps.crm.services import managed_user_ids, scope_queryset_for_user  # noqa: F401 (re-exported)

from .models import Call, CommunicationLog, EmailMessage, Notification, WhatsAppMessage
from .providers.a1routes import A1RoutesClient, A1RoutesError
from .providers.whatsapp import WhatsAppClient, WhatsAppError

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Contact-detail resolution (the privacy boundary)
# --------------------------------------------------------------------------
#
# THE RULE: a caller identifies WHO to contact (a `Customer`, `Lead` or
# `ContactPerson` — always by object/ID), and this module resolves WHAT
# address/number to actually use, server-side, from the database. The
# resolved value is used to talk to the provider and stored on the message
# row (the provider genuinely requires it, and a historical record of
# where a message actually went is an audit fact), but it is NEVER
# serialized back to an Employee — see `serializers.py`.
#
# Nothing here logs a resolved address or number: every log line in this
# module identifies a communication by primary keys and provider ids only.


class ContactResolutionError(ValueError):
    """Raised when a contact target has no usable address/number for the
    requested channel — a `ValueError` subclass so every existing caller
    that already catches `ValueError` from these services keeps working.
    """


def _entity_label(entity):
    """A safe, employee-visible description of a contact target: never the
    address/number, only the entity type and primary key.
    """
    if entity is None:
        return "unknown recipient"
    return f"{entity._meta.label_lower}#{entity.pk}"


def resolve_recipient_email(entity):
    """Return `entity`'s real email address, read straight from the
    database. Raises `ContactResolutionError` when the entity carries no
    address (or is not a contactable entity at all).
    """
    address = (getattr(entity, "email", "") or "").strip()
    if not address:
        raise ContactResolutionError(
            f"{_entity_label(entity)} has no email address on file."
        )
    return address


def resolve_recipient_phone(entity):
    """Return `entity`'s real phone number (also used as its WhatsApp
    number — this project stores one number per contact), read straight
    from the database. Raises `ContactResolutionError` when absent.
    """
    number = (getattr(entity, "phone", "") or "").strip()
    if not number:
        raise ContactResolutionError(
            f"{_entity_label(entity)} has no phone number on file."
        )
    return number


def contact_capabilities(entity):
    """``{"can_email": bool, "can_call": bool, "can_whatsapp": bool}`` for
    `entity` — the safe, boolean-only shape an employee-facing API may
    return in place of the values themselves.
    """
    has_email = bool((getattr(entity, "email", "") or "").strip())
    has_phone = bool((getattr(entity, "phone", "") or "").strip())
    return {"can_email": has_email, "can_call": has_phone, "can_whatsapp": has_phone}


# --------------------------------------------------------------------------
# Reply-To routing (inbound email)
# --------------------------------------------------------------------------


def generate_reply_token():
    """A fresh, unguessable token for one outbound message's Reply-To
    address. ``secrets.token_hex`` (not ``random``) because this token is
    the only thing standing between an arbitrary internet sender and an
    inbound message being attached to a real conversation.
    """
    return secrets.token_hex(16)


def reply_to_address(message):
    """The CRM-owned ``Reply-To`` address for `message`, or ``None`` when
    inbound-email routing is not configured (``INBOUND_EMAIL_DOMAIN``
    empty — the default).

    The customer replies to *us*, at an address that identifies the
    conversation by opaque token, so the reply never has to be routed
    through — or reveal — the employee's own mailbox, and the employee
    never handles the customer's address to reply.
    """
    domain = getattr(settings, "INBOUND_EMAIL_DOMAIN", "")
    if not domain or not message.reply_token:
        return None
    local_part = getattr(settings, "INBOUND_EMAIL_LOCAL_PART_PREFIX", "reply")
    return f"{local_part}+{message.reply_token}@{domain}"


def parse_reply_token(address):
    """Extract the reply token from an inbound envelope recipient such as
    ``reply+ab12...@crm.example.com``. Returns ``""`` when the address
    doesn't match the CRM's own Reply-To scheme — the caller treats that
    as "not ours", never as "trust whatever else the payload claimed".
    """
    if not address or "@" not in address:
        return ""
    local_part = address.rsplit("@", 1)[0]
    if "+" not in local_part:
        return ""
    return local_part.rsplit("+", 1)[1].strip()


# --------------------------------------------------------------------------
# Template rendering
# --------------------------------------------------------------------------

#: Matches ``{{field_name}}`` — deliberately simple (a bare word between
#: double braces), not a full template language. See EmailTemplate's own
#: docstring for why a full template engine (Django Template Language,
#: Jinja2) is NOT used here.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_template(template, context=None):
    """Render `template`'s `subject`/`body` against `context` (a plain
    dict), substituting every ``{{key}}`` with ``str(context[key])``.

    A placeholder whose key is missing from `context` is left UNCHANGED
    (e.g. ``{{unknown}}`` stays literally ``{{unknown}}``) rather than
    raising — a caller rendering a template against a partial context
    (e.g. previewing before all merge fields are known) gets a usable,
    partially-rendered result instead of a hard failure. Returns
    ``(subject, body)``, NOT a saved `EmailMessage` — persisting the
    rendered result is `queue_email()`'s job, keeping "render text" and
    "create a database row" as two independently testable operations.
    """
    context = context or {}

    def _substitute(match):
        key = match.group(1)
        return str(context[key]) if key in context else match.group(0)

    subject = _PLACEHOLDER_RE.sub(_substitute, template.subject)
    body = _PLACEHOLDER_RE.sub(_substitute, template.body)
    return subject, body


# --------------------------------------------------------------------------
# Email queueing + sending
# --------------------------------------------------------------------------


def queue_email(to_email=None, *, template=None, context=None, subject=None, body=None, owner=None, related_object=None):
    """Create a QUEUED `EmailMessage`, either rendered from `template` (+
    `context`) or from an explicit `subject`/`body` pair. Exactly one of
    the two input shapes must be usable — raises `ValueError` if neither
    `template` nor both `subject`/`body` are supplied, the same up-front
    "friendlier than a raw IntegrityError/AttributeError" validation shape
    CP13's `add_pricebook_entry()`/CP14's `create_reminder()` established.

    ``to_email`` is now OPTIONAL: when omitted (the employee-facing path),
    the recipient is resolved server-side from ``related_object`` via
    ``resolve_recipient_email()``, so a caller only ever has to know WHICH
    customer/lead to write to, never their actual address. It remains
    accepted (and unchanged in behavior) for the internal callers that
    legitimately already hold an address — `apps.workflows`' automation
    action, and a self-addressed digest — so no existing integration
    breaks.

    This is the "queueing abstraction" CP15 asks for: creating the
    record of an email to be sent is entirely separate from actually
    attempting delivery (`send_queued_email()`, below) — a caller can
    queue many emails and send them later, in a batch, or via a future
    background worker, without this function knowing or caring how
    sending eventually happens.
    """
    if template is not None:
        subject, body = render_template(template, context)
    elif subject is None or body is None:
        raise ValueError("Provide either a template, or both subject and body.")

    extra_fields = {}
    if related_object is not None:
        extra_fields["content_type"] = ContentType.objects.get_for_model(related_object)
        extra_fields["object_id"] = related_object.pk

    if not to_email:
        if related_object is None:
            raise ContactResolutionError(
                "Provide a related contact (customer/lead/contact) to resolve the recipient from."
            )
        to_email = resolve_recipient_email(related_object)

    return EmailMessage.objects.create(
        template=template,
        owner=owner,
        to_email=to_email,
        subject=subject,
        body=body,
        direction=EmailMessage.Direction.OUTBOUND,
        reply_token=generate_reply_token(),
        **extra_fields,
    )


def send_queued_email(message, *, send_func=None):
    """Attempt delivery of a QUEUED `EmailMessage`.

    `send_func` defaults to a thin wrapper around Django's
    `django.core.mail.send_mail()` — injectable so tests (and any future
    caller) never need a real SMTP server to exercise this function's
    actual behavior (updating `status`/`sent_at`/`error_message`), the
    same "inject the external dependency" shape this project has used
    everywhere a real network/DB call would otherwise make a unit
    untestable. Any exception `send_func` raises is caught: the message is
    marked FAILED with `error_message` set, and this function does NOT
    re-raise — a failed send is a recorded FACT about the message, not a
    caller-facing crash (the caller can inspect `message.status` and
    retry). Raises `ValueError` (not caught) if `message` is already SENT
    — re-sending a sent email is a caller error, the same "already closed"
    guard shape as CP11's `mark_won()`/CP14's `complete_task()`.

    Every successful or failed attempt is recorded in `CommunicationLog`
    (`log_communication()`) — the unified cross-channel audit trail this
    checkpoint's "communication logging" requirement asks for, written
    here automatically rather than left for callers to remember.
    """
    if message.status == EmailMessage.Status.SENT:
        raise ValueError("This email has already been sent.")

    send_func = send_func or _default_send_func

    try:
        send_func(message)
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any backend failure is "FAILED", not a crash
        message.status = EmailMessage.Status.FAILED
        message.error_message = str(exc)
        message.save(update_fields=["status", "error_message", "updated_at"])
    else:
        message.status = EmailMessage.Status.SENT
        message.sent_at = timezone.now()
        message.save(update_fields=["status", "sent_at", "updated_at"])

    log_communication(
        channel=CommunicationLog.Channel.EMAIL,
        summary=f"Email {message.status.lower()}: {message.subject}",
        actor=message.owner,
        related_object=message.related_object,
        occurred_at=message.sent_at,
    )
    return message


def _default_send_func(message):
    """The real (non-test) delivery path — Django's own mail machinery,
    using whatever `EMAIL_BACKEND`/`DEFAULT_FROM_EMAIL` the project's
    settings configure (no SMTP credentials are hardcoded here).

    Uses `django.core.mail.EmailMessage` rather than the older
    `send_mail()` shortcut for exactly one reason: `send_mail()` cannot
    set a ``Reply-To`` header, and the CRM-owned Reply-To address is what
    makes a customer's reply routable back to this conversation without
    the employee's mailbox — or the customer's address — being involved
    (see `reply_to_address()`). Everything else about delivery is
    unchanged.
    """
    reply_to = reply_to_address(message)
    email = DjangoEmailMessage(
        subject=message.subject,
        body=message.body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        to=[message.to_email],
        reply_to=[reply_to] if reply_to else None,
    )
    email.send(fail_silently=False)


# --------------------------------------------------------------------------
# Inbound email (customer replies)
# --------------------------------------------------------------------------

#: Header-ish lines a naive mail-to-text conversion tends to leave at the
#: top of a reply body. Stripped before an inbound body is ever stored,
#: because those lines are exactly where the customer's own address would
#: otherwise smuggle itself into employee-visible content.
_INBOUND_HEADER_RE = re.compile(
    r"^\s*(from|to|cc|bcc|reply-to|sender|return-path|x-[\w-]+)\s*:.*$",
    re.IGNORECASE | re.MULTILINE,
)

#: A bare email address anywhere in an inbound body.
_EMAIL_IN_TEXT_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def sanitize_inbound_body(raw_body, *, redaction="[contact detail removed]"):
    """Strip mail headers and redact any bare email address out of an
    inbound reply body.

    An inbound provider payload is untrusted, arbitrary text that WILL
    contain the customer's own address (in headers, in a quoted "On ...
    wrote:" block, or in a signature). Because the stored body is
    employee-visible, sanitizing is not cosmetic — it is the difference
    between "the employee sees the reply" and "the employee is handed the
    address". Deliberately conservative: it removes/redacts rather than
    attempting to reconstruct a pretty plain-text reply.
    """
    body = _INBOUND_HEADER_RE.sub("", raw_body or "")
    body = _EMAIL_IN_TEXT_RE.sub(redaction, body)
    return body.strip()


def record_inbound_email(payload):
    """Store one inbound customer reply, identified ONLY by the CRM's own
    Reply-To token.

    `payload` is the provider's parsed webhook body (see
    `apps.communications.views.InboundEmailWebhookView`, which verifies
    its signature before this is ever called). The recipient address the
    provider delivered to (``to``/``recipient``) carries the reply token;
    the token — not any lead/conversation id the caller claims — is what
    selects the conversation, so an external client cannot attach a
    fabricated message to an arbitrary lead by guessing IDs.

    Returns the created INBOUND `EmailMessage`, or ``None`` when the token
    is missing/unknown (an unrecognized reply is ignored, never raised —
    same contract as the A1 Routes/WhatsApp webhook appliers).
    """
    recipient = payload.get("to") or payload.get("recipient") or ""
    token = parse_reply_token(recipient)
    if not token:
        return None

    original = (
        EmailMessage.objects.filter(reply_token=token, direction=EmailMessage.Direction.OUTBOUND)
        .order_by("-created_at")
        .first()
    )
    if original is None:
        logger.info("Inbound email ignored: no conversation matches the supplied reply token.")
        return None

    # The SUBJECT needs the same redaction as the body, not just the body:
    # a mail client's own "Re: Quote from alice@example.com" reply subject
    # carries the customer's address, and the subject is what a
    # Notification title/message and a sent-mail list render.
    subject = _EMAIL_IN_TEXT_RE.sub(
        "[contact detail removed]", str(payload.get("subject") or f"Re: {original.subject}")
    )[:255]
    body = sanitize_inbound_body(payload.get("text") or payload.get("body") or "")

    reply = EmailMessage.objects.create(
        template=None,
        owner=original.owner,
        # Deliberately the CRM's OWN inbound address, not the customer's
        # address: an inbound row's "to_email" is where WE received it.
        to_email=recipient,
        subject=subject,
        body=body,
        status=EmailMessage.Status.SENT,
        sent_at=timezone.now(),
        direction=EmailMessage.Direction.INBOUND,
        in_reply_to=original,
        content_type_id=original.content_type_id,
        object_id=original.object_id,
    )

    log_communication(
        channel=CommunicationLog.Channel.EMAIL,
        summary=f"Email reply received (email #{original.pk})",
        actor=original.owner,
        related_object=original.related_object,
        occurred_at=reply.created_at,
    )
    if original.owner_id is not None:
        create_notification(
            original.owner,
            Notification.NotificationType.INFO,
            "New email reply received",
            message=subject,
            related_object=original.related_object,
        )
    logger.info("Inbound email stored as message %s in reply to %s.", reply.pk, original.pk)
    return reply


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------


def create_notification(recipient, notification_type, title, *, message="", related_object=None):
    """Create a `Notification` for `recipient`. Logs the creation via
    `log_communication()` — same automatic audit-trail behavior as
    `send_queued_email()`.
    """
    extra_fields = {}
    if related_object is not None:
        extra_fields["content_type"] = ContentType.objects.get_for_model(related_object)
        extra_fields["object_id"] = related_object.pk

    notification = Notification.objects.create(
        recipient=recipient, notification_type=notification_type, title=title, message=message, **extra_fields
    )

    log_communication(
        channel=CommunicationLog.Channel.NOTIFICATION,
        summary=title,
        actor=None,
        related_object=related_object,
        occurred_at=notification.created_at,
    )
    return notification


def mark_notification_read(notification):
    """Mark `notification` read. Idempotent on purpose — same reasoning as
    CP14's `mark_reminder_sent()`: re-marking an already-read notification
    read breaks no invariant.
    """
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


def mark_notification_unread(notification):
    """Reverse `mark_notification_read()`."""
    notification.is_read = False
    notification.read_at = None
    notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


# --------------------------------------------------------------------------
# Communication logging
# --------------------------------------------------------------------------


def log_communication(*, channel, summary, actor=None, related_object=None, occurred_at=None):
    """Create a `CommunicationLog` entry. Called automatically by
    `send_queued_email()`/`create_notification()` — there is deliberately
    no API endpoint that lets a client call this directly (see
    `views.py`): `CommunicationLog` is the system's own record of what it
    did, not something a caller should be able to fabricate.
    """
    extra_fields = {}
    if related_object is not None:
        extra_fields["content_type"] = ContentType.objects.get_for_model(related_object)
        extra_fields["object_id"] = related_object.pk

    return CommunicationLog.objects.create(
        channel=channel, summary=summary, actor=actor, occurred_at=occurred_at or timezone.now(), **extra_fields
    )


def initiate_call(from_number, to_number=None, *, owner=None, related_object=None):
    """Create a `Call` and place it through A1 Routes.

    ``to_number`` is OPTIONAL: when omitted (the employee-facing path), it
    is resolved server-side from ``related_object`` via
    ``resolve_recipient_phone()`` — the employee's client says "call this
    lead", never "call this number", and the number is never returned to
    it. It stays accepted for internal callers that already legitimately
    hold a number.

    The `Call` row is created (``QUEUED``) BEFORE the provider is ever
    contacted, so a provider outage still leaves a real, queryable
    record of the attempt — the same "record the fact, don't lose it to
    a provider failure" contract `send_queued_email()` already
    established for SendGrid. A provider failure moves the row straight
    to ``FAILED`` with `error_message` set; it never raises out of this
    function (mirroring `send_queued_email()`'s own never-raises
    contract) — the caller always gets a `Call` instance back and reads
    `.status` to know what happened.
    """
    extra_fields = {}
    if related_object is not None:
        extra_fields["content_type"] = ContentType.objects.get_for_model(related_object)
        extra_fields["object_id"] = related_object.pk

    if not to_number:
        if related_object is None:
            raise ContactResolutionError(
                "Provide a related contact (customer/lead/contact) to resolve the number from."
            )
        to_number = resolve_recipient_phone(related_object)

    call = Call.objects.create(
        owner=owner,
        direction=Call.Direction.OUTBOUND,
        from_number=from_number,
        to_number=to_number,
        status=Call.Status.QUEUED,
        **extra_fields,
    )

    try:
        client = A1RoutesClient()
        provider_call_id = client.initiate_call(from_number, to_number)
    except A1RoutesError as exc:
        call.status = Call.Status.FAILED
        call.error_message = str(exc)
        call.save(update_fields=["status", "error_message", "updated_at"])
        return call

    call.provider_call_id = provider_call_id
    call.status = Call.Status.RINGING
    call.started_at = timezone.now()
    call.save(update_fields=["provider_call_id", "status", "started_at", "updated_at"])
    # The audit summary names the CALL, never the number: a
    # CommunicationLog row is employee-visible (see views.py).
    log_communication(
        channel=CommunicationLog.Channel.CALL,
        summary=f"Call placed (call #{call.pk})",
        actor=owner,
        related_object=call,
    )
    logger.info("Call %s placed to %s.", call.pk, _entity_label(related_object))
    return call


_A1ROUTES_STATUS_MAP = {
    "ringing": Call.Status.RINGING,
    "in-progress": Call.Status.IN_PROGRESS,
    "in_progress": Call.Status.IN_PROGRESS,
    "completed": Call.Status.COMPLETED,
    "failed": Call.Status.FAILED,
    "no-answer": Call.Status.NO_ANSWER,
    "no_answer": Call.Status.NO_ANSWER,
    "busy": Call.Status.BUSY,
}

#: Call status transitions that get their OWN `CommunicationLog` entry when
#: the provider reports them. ``QUEUED``/``RINGING`` are deliberately absent:
#: ``initiate_call()`` already logs "Call placed" at exactly that point in
#: the lifecycle, and logging RINGING too would mean two audit rows for one
#: event. What was missing before was everything AFTER placement — the
#: spec's CALL_CONNECTED/CALL_COMPLETED/CALL_FAILED events, which only the
#: provider can report and which previously overwrote ``Call.status`` in
#: place, leaving no historical record that the transition happened.
_CALL_AUDITED_TRANSITIONS = {
    Call.Status.IN_PROGRESS: "connected",
    Call.Status.COMPLETED: "completed",
    Call.Status.FAILED: "failed",
    Call.Status.NO_ANSWER: "not answered",
    Call.Status.BUSY: "busy",
}


def apply_a1routes_webhook_event(payload):
    """Update the matching `Call` from an A1 Routes webhook payload.
    Idempotent by design: re-applying the exact same event (same
    ``call_id`` + ``status``) is a no-op, not a duplicate side effect —
    the closest thing to replay protection available without a
    dedicated inbound-event log, on top of the webhook view's own
    signature verification (see ``views.py``).

    Returns the updated `Call`, or ``None`` if no matching call was
    found (an unknown ``call_id`` is logged by the caller, not raised
    here — a webhook handler should never 500 on data it doesn't
    recognize).
    """
    provider_call_id = payload.get("call_id")
    if not provider_call_id:
        return None

    call = Call.objects.filter(provider_call_id=provider_call_id).first()
    if call is None:
        return None

    new_status = _A1ROUTES_STATUS_MAP.get(str(payload.get("status", "")).lower())
    if new_status is None or new_status == call.status:
        return call  # unknown or already-applied status — no-op

    call.status = new_status
    update_fields = ["status", "updated_at"]
    if new_status in (Call.Status.COMPLETED, Call.Status.FAILED, Call.Status.NO_ANSWER, Call.Status.BUSY):
        call.ended_at = timezone.now()
        update_fields.append("ended_at")
        duration = payload.get("duration_seconds")
        if isinstance(duration, int):
            call.duration_seconds = duration
            update_fields.append("duration_seconds")
    call.save(update_fields=update_fields)

    # The provider is the AUTHORITATIVE source for what happened to a call
    # after it was placed, and this is the only code path that hears it —
    # so this is where the CALL_CONNECTED/COMPLETED/FAILED audit event has
    # to be written, following this app's own standing rule that the
    # service function causing a state change is the one that logs it (see
    # `log_communication()`). Safe against double-logging: the guard above
    # returns early when the status is unchanged, so a replayed webhook
    # writes nothing. Never names a number — see `initiate_call()`.
    transition_label = _CALL_AUDITED_TRANSITIONS.get(new_status)
    if transition_label is not None:
        duration_note = (
            f", {call.duration_seconds}s" if call.duration_seconds is not None else ""
        )
        log_communication(
            channel=CommunicationLog.Channel.CALL,
            summary=f"Call {transition_label} (call #{call.pk}{duration_note})",
            actor=call.owner,
            related_object=call,
        )
    return call


def send_whatsapp_message(to_number, body, *, owner=None, customer=None):
    """Create a `WhatsAppMessage` and send it through the WhatsApp Cloud
    API — identical shape/contract to `initiate_call()` above: the row
    is created ``QUEUED`` first, a provider failure moves it to
    ``FAILED`` with `error_message` set, and this never raises.

    ``to_number`` may be ``None``/empty, in which case it is resolved
    server-side from ``customer`` (``resolve_recipient_phone()``) — the
    employee-facing path passes a customer, never a number. Kept as the
    first POSITIONAL parameter so every existing caller is unaffected.
    """
    if not to_number:
        if customer is None:
            raise ContactResolutionError(
                "Provide a customer to resolve the WhatsApp number from."
            )
        to_number = resolve_recipient_phone(customer)

    message = WhatsAppMessage.objects.create(
        owner=owner,
        customer=customer,
        direction=WhatsAppMessage.Direction.OUTBOUND,
        sender="",  # filled in below once the client resolves WHATSAPP_PHONE_ID
        receiver=to_number,
        message=body,
        status=WhatsAppMessage.Status.QUEUED,
    )

    try:
        client = WhatsAppClient()
    except WhatsAppError as exc:
        message.status = WhatsAppMessage.Status.FAILED
        message.error_message = str(exc)
        message.save(update_fields=["status", "error_message", "updated_at"])
        return message

    message.sender = client.phone_id
    try:
        provider_message_id = client.send_message(to_number, body)
    except WhatsAppError as exc:
        message.status = WhatsAppMessage.Status.FAILED
        message.error_message = str(exc)
        message.save(update_fields=["sender", "status", "error_message", "updated_at"])
        return message

    message.provider_message_id = provider_message_id
    message.status = WhatsAppMessage.Status.SENT
    message.save(update_fields=["sender", "provider_message_id", "status", "updated_at"])
    # Never the number — see initiate_call()'s equivalent comment.
    log_communication(
        channel=CommunicationLog.Channel.WHATSAPP,
        summary=f"WhatsApp message sent (message #{message.pk})",
        actor=owner,
        related_object=message,
    )
    logger.info("WhatsApp message %s sent to %s.", message.pk, _entity_label(customer))
    return message


_WHATSAPP_STATUS_MAP = {
    "sent": WhatsAppMessage.Status.SENT,
    "delivered": WhatsAppMessage.Status.DELIVERED,
    "read": WhatsAppMessage.Status.READ,
    "failed": WhatsAppMessage.Status.FAILED,
}

#: WhatsApp status transitions that get their own `CommunicationLog`
#: entry. ``SENT`` is absent for the same reason ``RINGING`` is absent from
#: `_CALL_AUDITED_TRANSITIONS`: `send_whatsapp_message()` already logs the
#: send. DELIVERED/READ/FAILED are the spec's WHATSAPP_DELIVERED/READ/
#: FAILED events, and only the provider can report them.
_WHATSAPP_AUDITED_TRANSITIONS = {
    WhatsAppMessage.Status.DELIVERED: "delivered",
    WhatsAppMessage.Status.READ: "read",
    WhatsAppMessage.Status.FAILED: "failed",
}


def apply_whatsapp_webhook_event(payload):
    """Update the matching `WhatsAppMessage` (by `provider_message_id`)
    from a WhatsApp Cloud API webhook status payload — same idempotent-
    by-value-comparison contract as `apply_a1routes_webhook_event()`.
    Returns the updated message, or ``None`` if no matching row exists (a
    status update for a message id this app doesn't recognize). Inbound
    messages arrive on the SAME webhook but under a different key and are
    handled by `record_inbound_whatsapp()`, not here.
    """
    provider_message_id = payload.get("id")
    if not provider_message_id:
        return None

    message = WhatsAppMessage.objects.filter(provider_message_id=provider_message_id).first()
    if message is None:
        return None

    new_status = _WHATSAPP_STATUS_MAP.get(str(payload.get("status", "")).lower())
    if new_status is None or new_status == message.status:
        return message

    message.status = new_status
    message.save(update_fields=["status", "updated_at"])

    # See `apply_a1routes_webhook_event()`'s equivalent block — same
    # reasoning, same idempotency guarantee (the unchanged-status guard
    # above returns before reaching here on a replay).
    transition_label = _WHATSAPP_AUDITED_TRANSITIONS.get(new_status)
    if transition_label is not None:
        log_communication(
            channel=CommunicationLog.Channel.WHATSAPP,
            summary=f"WhatsApp message {transition_label} (message #{message.pk})",
            actor=message.owner,
            related_object=message,
        )
    return message


def _match_customer_by_phone(number):
    """Find the `Customer` whose stored phone number IS `number`.

    Deliberately EXACT-match only (against the raw value and its
    ``+``-prefixed/unprefixed variants, since providers differ on that one
    character): a fuzzy "ends with these digits" match would let a caller
    who controls the ``from`` field of a webhook payload attach a
    fabricated inbound message to a customer whose number merely shares a
    suffix. An unmatched number simply yields ``None`` and the message is
    stored unattached — never guessed at.
    """
    from apps.crm.models import Customer

    number = (number or "").strip()
    if not number:
        return None
    candidates = {number, f"+{number.lstrip('+')}", number.lstrip("+")}
    return Customer.objects.filter(phone__in=candidates).first()


def record_inbound_whatsapp(payload, *, receiver=""):
    """Store one inbound WhatsApp message (a customer's REPLY) from a
    single ``entry[].changes[].value.messages[]`` element of a Meta Cloud
    API webhook body.

    Same trust model and same contract as `record_inbound_email()`:

    - The caller (``views.WhatsAppWebhookView``) has already verified the
      payload's ``X-Hub-Signature-256`` before this runs.
    - The conversation is resolved SERVER-SIDE from the sending number
      (`_match_customer_by_phone()`); any customer/lead id present in the
      payload is ignored outright, because a webhook body is
      attacker-controlled input.
    - Returns ``None`` rather than raising for anything unrecognized, so a
      webhook handler never 500s on data it doesn't understand.
    - Idempotent on ``provider_message_id``: Meta retries deliveries, and
      a retry must not create a second copy of the same reply.

    The stored ``sender`` is the customer's real number — an audit fact,
    and already masked out of every Employee-facing response by
    ``WhatsAppMessageSerializer.pii_fields``.
    """
    provider_message_id = str(payload.get("id") or "").strip()
    from_number = str(payload.get("from") or "").strip()
    if not from_number:
        return None

    if provider_message_id and WhatsAppMessage.objects.filter(
        provider_message_id=provider_message_id, direction=WhatsAppMessage.Direction.INBOUND
    ).exists():
        return None

    text = payload.get("text")
    body = str(text.get("body") or "") if isinstance(text, dict) else ""
    if not body:
        # Non-text messages (media, reactions, location, ...) are still a
        # real communication touchpoint the audit trail must not lose, so
        # the row is created with a neutral type marker instead of being
        # dropped. The provider's own type string is the only thing
        # trusted from the payload here, and it is not PII.
        body = f"[{str(payload.get('type') or 'unsupported')} message]"

    customer = _match_customer_by_phone(from_number)
    owner = customer.owner if customer is not None and customer.owner_id else None

    message = WhatsAppMessage.objects.create(
        owner=owner,
        customer=customer,
        direction=WhatsAppMessage.Direction.INBOUND,
        sender=from_number,
        receiver=receiver or "",
        message=body,
        # An inbound message has already arrived — there is no delivery
        # attempt of ours left to track, so it lands terminal.
        status=WhatsAppMessage.Status.DELIVERED,
        provider_message_id=provider_message_id,
    )

    log_communication(
        channel=CommunicationLog.Channel.WHATSAPP,
        summary=f"WhatsApp reply received (message #{message.pk})",
        actor=owner,
        related_object=message,
    )
    if owner is not None:
        create_notification(
            owner,
            Notification.NotificationType.INFO,
            "New WhatsApp reply received",
            message=body[:200],
            related_object=customer,
        )
    logger.info("Inbound WhatsApp message stored as %s for %s.", message.pk, _entity_label(customer))
    return message


# --------------------------------------------------------------------------
# Unified communication service (entity-addressed, provider-abstracted)
# --------------------------------------------------------------------------
#
# One entry point per channel, all with the SAME first argument — the
# contact ENTITY, never a raw address/number. Each one is a thin
# composition of the channel functions above (which keep their own
# contracts unchanged for existing callers); this section exists so a
# caller — a view, a workflow action, a future background job — has a
# single obvious "communicate with this lead" API that makes the raw
# address/number impossible to pass in and impossible to get back out.


def send_email_to_entity(entity, *, template=None, context=None, subject=None, body=None, owner=None):
    """Queue an email to `entity` (a `Customer`/`Lead`/`ContactPerson`).
    Resolves the address internally; raises `ContactResolutionError` when
    the entity has none.
    """
    return queue_email(
        template=template, context=context, subject=subject, body=body, owner=owner, related_object=entity
    )


def call_entity(entity, *, owner=None, from_number=None):
    """Place a call to `entity`, resolving the number internally.
    ``from_number`` defaults to the configured CRM trunk number — never
    something a client supplies.
    """
    if from_number is None:
        from_number = getattr(settings, "A1ROUTES_DEFAULT_FROM_NUMBER", "")
    return initiate_call(from_number, None, owner=owner, related_object=entity)


def send_whatsapp_to_entity(entity, body, *, owner=None):
    """Send a WhatsApp message to `entity`, resolving the number
    internally. `WhatsAppMessage` only models a `Customer` relation, so a
    non-`Customer` entity is still contactable but not back-linked.
    """
    from apps.crm.models import Customer

    customer = entity if isinstance(entity, Customer) else None
    return send_whatsapp_message(
        resolve_recipient_phone(entity), body, owner=owner, customer=customer
    )


__all__ = [
    "managed_user_ids",
    "scope_queryset_for_user",
    "ContactResolutionError",
    "resolve_recipient_email",
    "resolve_recipient_phone",
    "contact_capabilities",
    "generate_reply_token",
    "reply_to_address",
    "parse_reply_token",
    "sanitize_inbound_body",
    "record_inbound_email",
    "send_email_to_entity",
    "call_entity",
    "send_whatsapp_to_entity",
    "render_template",
    "queue_email",
    "send_queued_email",
    "create_notification",
    "mark_notification_read",
    "mark_notification_unread",
    "log_communication",
    "initiate_call",
    "apply_a1routes_webhook_event",
    "send_whatsapp_message",
    "apply_whatsapp_webhook_event",
    "record_inbound_whatsapp",
]
