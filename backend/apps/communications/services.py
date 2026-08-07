"""CP15: reusable service functions for the communications domain.

Following the CP9-CP14 pattern: narrow, single-purpose, independently
testable functions for operations with real behavior beyond a single ORM
call.

Ownership scoping is NOT reimplemented — CP10's `managed_user_ids()`/
`scope_queryset_for_user()` are imported directly from `apps.crm.services`,
exactly as every checkpoint since CP12 has done, per this project's
standing "reuse existing infrastructure, do not duplicate logic" rule.
"""
import re

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.utils import timezone

from apps.crm.services import managed_user_ids, scope_queryset_for_user  # noqa: F401 (re-exported)

from .models import CommunicationLog, EmailMessage, Notification

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


def queue_email(to_email, *, template=None, context=None, subject=None, body=None, owner=None, related_object=None):
    """Create a QUEUED `EmailMessage`, either rendered from `template` (+
    `context`) or from an explicit `subject`/`body` pair. Exactly one of
    the two input shapes must be usable — raises `ValueError` if neither
    `template` nor both `subject`/`body` are supplied, the same up-front
    "friendlier than a raw IntegrityError/AttributeError" validation shape
    CP13's `add_pricebook_entry()`/CP14's `create_reminder()` established.

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

    return EmailMessage.objects.create(
        template=template, owner=owner, to_email=to_email, subject=subject, body=body, **extra_fields
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
    """The real (non-test) delivery path — Django's own `send_mail()`,
    using whatever `EMAIL_BACKEND`/`DEFAULT_FROM_EMAIL` the project's
    settings configure (unchanged by this checkpoint; no SMTP credentials
    are hardcoded here).
    """
    send_mail(
        message.subject,
        message.body,
        getattr(settings, "DEFAULT_FROM_EMAIL", None),
        [message.to_email],
        fail_silently=False,
    )


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


__all__ = [
    "managed_user_ids",
    "scope_queryset_for_user",
    "render_template",
    "queue_email",
    "send_queued_email",
    "create_notification",
    "mark_notification_read",
    "mark_notification_unread",
    "log_communication",
]
