"""CP15: the communications domain's REST API.

Two viewset bases, matching the two access shapes `permissions.py`
documents:

- `_ReferenceDataModelViewSet` (`EmailTemplate` only) — no ownership
  scoping. Its shared no-PUT/active-vs-unfiltered shape now lives in
  `apps.core.views.ReferenceDataModelViewSetMixin` (factored out at CP20
  after the third independent occurrence of it — see that mixin's own
  docstring); only `permission_classes` is declared here, since
  `EmailTemplateWritePermission` is this app's own composition, not
  something `apps.catalog`'s or `apps.system`'s equivalent viewsets have
  any business depending on.
- CP10's `_CrmModelViewSet` (`apps.crm.views`), reused directly for
  `EmailMessage`/`Notification`/`CommunicationLog` — all three have a real
  or delegating `owner`, the same cross-app reuse CP12/CP14 already
  established.
"""
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.serializers import pii_masking_required
from apps.core.utils import stamp_audit_fields
from apps.core.views import PiiSafeSearchMixin, ReferenceDataModelViewSetMixin
from apps.crm.permissions import assert_object_accessible
from apps.crm.views import _CrmModelViewSet

from .filters import (
    CallFilterSet,
    CommunicationLogFilterSet,
    EmailMessageFilterSet,
    EmailTemplateFilterSet,
    NotificationFilterSet,
    WhatsAppMessageFilterSet,
)
from .models import Call, CommunicationLog, EmailMessage, EmailTemplate, Notification, WhatsAppMessage
from .permissions import EmailTemplateWritePermission
from .providers.a1routes import verify_webhook_signature as verify_a1routes_signature
from .providers.inbound_email import verify_webhook_signature as verify_inbound_email_signature
from .providers.whatsapp import (
    verify_webhook_signature as verify_whatsapp_signature,
    verify_webhook_subscription_token,
)
from .serializers import (
    CallSerializer,
    CommunicationLogSerializer,
    EmailMessageQueueSerializer,
    EmailMessageSerializer,
    EmailTemplateSerializer,
    InitiateCallSerializer,
    NotificationSerializer,
    SendWhatsAppMessageSerializer,
    WhatsAppMessageSerializer,
)
from .services import (
    ContactResolutionError,
    apply_a1routes_webhook_event,
    apply_whatsapp_webhook_event,
    create_notification,
    initiate_call,
    mark_notification_read,
    mark_notification_unread,
    queue_email,
    record_inbound_email,
    record_inbound_whatsapp,
    send_queued_email,
    send_whatsapp_to_entity,
)


def _resolve_contact_target(request, data):
    """Resolve the contact ENTITY an employee-facing communication request
    names, and prove the requester is allowed to reach it.

    Accepts either a named relation (``customer``/``lead``/``contact``) or
    this app's pre-existing generic ``content_type``+``object_id`` pair, so
    no existing client shape stops working. Returns ``None`` when the
    request names no target at all (the self-addressed-email case).

    ``assert_object_accessible()`` (CP6/CP9, unchanged) is the important
    line: without it, Employee B could name Employee A's customer by ID
    and make the backend read that customer's address/number and contact
    them — an authorization hole that the OLD raw-``to_email``/
    ``to_number`` API hid only because the caller had to already know the
    value. Resolving PII server-side makes the ownership check mandatory,
    and it raises ``Http404`` (not 403) for an inaccessible object, the
    same "don't confirm the row exists" behavior every other CRM endpoint
    already has.
    """
    target = data.get("customer") or data.get("lead") or data.get("contact")
    if target is None:
        content_type = data.get("content_type")
        object_id = data.get("object_id")
        if content_type is None or object_id is None:
            return None
        try:
            target = content_type.get_object_for_this_type(pk=object_id)
        except ObjectDoesNotExist as exc:
            # A nonexistent target is a 404, not a 500 — and it reads the
            # same to the client as an INACCESSIBLE one, so this pair
            # can't be used to enumerate which IDs exist.
            raise Http404 from exc

    assert_object_accessible(request, target)
    return target


class _ReferenceDataModelViewSet(ReferenceDataModelViewSetMixin, viewsets.ModelViewSet):
    """Shared reference-data base — see this module's own docstring."""

    permission_classes = [IsAuthenticated, EmailTemplateWritePermission]


class EmailTemplateViewSet(_ReferenceDataModelViewSet):
    base_manager = EmailTemplate.objects
    base_active_manager = EmailTemplate.active_objects
    serializer_class = EmailTemplateSerializer
    filterset_class = EmailTemplateFilterSet
    search_fields = ["name", "subject"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]


class EmailMessageViewSet(PiiSafeSearchMixin, _CrmModelViewSet):
    """`create()` is overridden entirely (not just `perform_create()`):
    queueing an email accepts a `template`(+`context`) OR `subject`+`body`
    input union (`EmailMessageQueueSerializer`) that doesn't map onto
    `EmailMessage`'s own flat field list the way ordinary creation does —
    see that serializer's docstring.
    """

    base_manager = EmailMessage.objects
    base_active_manager = EmailMessage.active_objects
    serializer_class = EmailMessageSerializer
    filterset_class = EmailMessageFilterSet
    full_search_fields = ["subject", "to_email"]
    pii_search_fields = ("to_email",)
    ordering_fields = ["created_at", "sent_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("owner", "template", "content_type")

    @extend_schema(request=EmailMessageQueueSerializer, responses={201: EmailMessageSerializer})
    def create(self, request, *args, **kwargs):
        input_serializer = EmailMessageQueueSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        related_object = _resolve_contact_target(request, data)

        to_email = data.get("to_email")
        if to_email:
            if related_object is not None:
                return Response(
                    {"detail": "Provide either a contact to email, or `to_email` for self-addressed mail — not both."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # Self-addressed mail only. A Manager/Super Admin may address
            # anyone (they can already read customer addresses); an
            # Employee may address ONLY their own signed-in mailbox, so
            # this endpoint can never be used as a relay to an arbitrary
            # third party, nor as a confirmation oracle for a guessed
            # customer address.
            own_address = (getattr(request.user, "email", "") or "").strip().lower()
            if pii_masking_required(request) and to_email.strip().lower() != own_address:
                return Response(
                    {
                        "detail": (
                            "`to_email` may only be your own address. "
                            "Email a customer or lead by passing `customer`, `lead` or `contact`."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            message = queue_email(
                to_email,
                template=data.get("template"),
                context=data.get("context"),
                subject=data.get("subject"),
                body=data.get("body"),
                owner=request.user,
                related_object=related_object,
            )
        except ContactResolutionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        stamp_audit_fields(message, request.user, creating=True)
        message.save()

        output_serializer = self.get_serializer(message)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: EmailMessageSerializer})
    @action(detail=True, methods=["post"])
    def send(self, request, *args, **kwargs):
        """``POST /email-messages/<id>/send/`` — attempts delivery
        (``services.send_queued_email()``); rejects an already-sent message.
        """
        message = self.get_object()
        try:
            send_queued_email(message)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(message)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationViewSet(_CrmModelViewSet):
    base_manager = Notification.objects
    base_active_manager = Notification.active_objects
    serializer_class = NotificationSerializer
    filterset_class = NotificationFilterSet
    owner_field = "recipient"
    search_fields = ["title", "message"]
    ordering_fields = ["created_at", "is_read"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("recipient", "content_type")

    def perform_create(self, serializer):
        """Routes creation through ``services.create_notification()`` —
        real behavior: automatically writes a ``CommunicationLog`` entry
        (this checkpoint's "communication logging" requirement), which a
        bare ``serializer.save()`` would skip.
        """
        data = dict(serializer.validated_data)
        recipient = data.pop("recipient")
        notification_type = data.pop("notification_type")
        title = data.pop("title")
        message = data.pop("message", "")
        related_object = None
        content_type = data.pop("content_type", None)
        object_id = data.pop("object_id", None)
        if content_type is not None and object_id is not None:
            related_object = content_type.get_object_for_this_type(pk=object_id)

        notification = create_notification(
            recipient, notification_type, title, message=message, related_object=related_object
        )
        stamp_audit_fields(notification, self.request.user, creating=True)
        notification.save()
        serializer.instance = notification

    @extend_schema(request=None, responses={200: NotificationSerializer})
    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, *args, **kwargs):
        notification = self.get_object()
        mark_notification_read(notification)
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: NotificationSerializer})
    @action(detail=True, methods=["post"], url_path="mark-unread")
    def mark_unread(self, request, *args, **kwargs):
        notification = self.get_object()
        mark_notification_unread(notification)
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CommunicationLogViewSet(_CrmModelViewSet):
    """Read-only — ``http_method_names`` excludes every write verb, so
    there is no create/update/delete/restore/hard-delete route at all
    (DRF returns 405 for any of them), matching this model's own
    "written automatically by services, never by a client" design (see
    ``models.py``'s `CommunicationLog` docstring).
    """

    base_manager = CommunicationLog.objects
    base_active_manager = CommunicationLog.active_objects
    serializer_class = CommunicationLogSerializer
    filterset_class = CommunicationLogFilterSet
    owner_field = "actor"
    http_method_names = ["get", "head", "options"]
    search_fields = ["summary"]
    ordering_fields = ["occurred_at"]
    ordering = ["-occurred_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("actor", "content_type")


class CallViewSet(PiiSafeSearchMixin, _CrmModelViewSet):
    """Final production operations pass: A1 Routes SIP integration.

    ``create()`` is overridden entirely (not just ``perform_create()``)
    — same reasoning as ``EmailMessageViewSet.create()``: initiating a
    call accepts only ``to_number`` (+ an optional related object), a
    different shape from ``Call``'s own full field list, most of which
    (``provider_call_id``, ``status``, timing) only the provider can
    supply. No SIP credential ever appears in the request or response —
    ``services.initiate_call()`` reads them from the environment only.
    """

    base_manager = Call.objects
    base_active_manager = Call.active_objects
    serializer_class = CallSerializer
    filterset_class = CallFilterSet
    full_search_fields = ["from_number", "to_number", "provider_call_id"]
    pii_search_fields = ("from_number", "to_number")
    ordering_fields = ["created_at", "started_at", "status"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "head", "options"]

    def get_throttles(self):
        # Rate-limited: placing a call is a real, billable external-
        # provider operation — same "expensive_operation" scope as
        # report execution/import/export/merge/payment recording (see
        # config/settings/base.py's own docstring on that scope).
        if self.action == "create":
            self.throttle_scope = "expensive_operation"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return super().get_queryset().select_related("owner", "content_type")

    @extend_schema(request=InitiateCallSerializer, responses={201: CallSerializer})
    def create(self, request, *args, **kwargs):
        """``POST /calls/`` — places an outbound call via A1 Routes
        (``services.initiate_call()``). Always returns 201: a provider
        failure is recorded on the `Call` row itself (``status=FAILED``,
        ``error_message`` set), not raised as an HTTP error — the same
        "the record of the attempt is the response" contract
        ``EmailMessageViewSet`` already uses for a send failure.
        """
        input_serializer = InitiateCallSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        related_object = _resolve_contact_target(request, data)

        from_number = getattr(settings, "A1ROUTES_DEFAULT_FROM_NUMBER", "")
        try:
            call = initiate_call(from_number, None, owner=request.user, related_object=related_object)
        except ContactResolutionError as exc:
            # "This contact has no number on file" is a client mistake
            # (400), not a provider failure — and the message names the
            # ENTITY, never a number.
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        stamp_audit_fields(call, request.user, creating=True)
        call.save()

        output_serializer = self.get_serializer(call)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class WhatsAppMessageViewSet(PiiSafeSearchMixin, _CrmModelViewSet):
    """Final production operations pass: WhatsApp Business API
    integration — identical shape/reasoning to ``CallViewSet`` above.
    """

    base_manager = WhatsAppMessage.objects
    base_active_manager = WhatsAppMessage.active_objects
    serializer_class = WhatsAppMessageSerializer
    filterset_class = WhatsAppMessageFilterSet
    full_search_fields = ["sender", "receiver", "message", "provider_message_id"]
    pii_search_fields = ("sender", "receiver")
    ordering_fields = ["created_at", "status"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "head", "options"]

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "expensive_operation"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        return super().get_queryset().select_related("owner", "customer")

    @extend_schema(request=SendWhatsAppMessageSerializer, responses={201: WhatsAppMessageSerializer})
    def create(self, request, *args, **kwargs):
        """``POST /whatsapp/send/`` — sends a WhatsApp message
        (``services.send_whatsapp_message()``). Same "the record of the
        attempt is the response, a provider failure is never a 5xx"
        contract as ``CallViewSet.create()``.
        """
        input_serializer = SendWhatsAppMessageSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data

        target = _resolve_contact_target(request, data)

        try:
            # The unified, entity-addressed entry point: it resolves the
            # WhatsApp number from `target` server-side and back-links the
            # row to the customer when the target IS a customer.
            message = send_whatsapp_to_entity(target, data["message"], owner=request.user)
        except ContactResolutionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        stamp_audit_fields(message, request.user, creating=True)
        message.save()

        output_serializer = self.get_serializer(message)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


# --------------------------------------------------------------------------
# Inbound provider webhooks
# --------------------------------------------------------------------------
#
# Neither webhook uses JWT (the provider has no user account) — each is
# authenticated entirely by its own signature scheme instead, verified
# against a secret read from the environment (never accepted from the
# request itself). Both are exempt from Django's CSRF check (an
# unauthenticated server-to-server POST can't carry a CSRF token) via
# DRF's own `APIView`, which already exempts API views from Django's
# session-based CSRF enforcement — see DRF's own `csrf_exempt` wrapping
# of `APIView.as_view()`.


class A1RoutesWebhookView(APIView):
    """``POST /api/v1/webhooks/a1routes/`` — A1 Routes' own call-status
    callback. Verifies ``X-A1Routes-Signature`` (HMAC-SHA256 over the
    raw body, keyed by ``A1ROUTES_WEBHOOK_SECRET``) before touching the
    database at all; an invalid/missing signature is a 401, not a 400 —
    a client that can't prove it's A1 Routes gets no information about
    whether the ``call_id`` it sent even exists.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "expensive_operation"

    @extend_schema(request=None, responses={200: dict, 401: dict})
    def post(self, request, *args, **kwargs):
        signature = request.headers.get("X-A1Routes-Signature", "")
        if not verify_a1routes_signature(request.body, signature):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

        call = apply_a1routes_webhook_event(request.data)
        if call is None:
            # An unrecognized call_id or malformed payload is not this
            # endpoint's fault to raise a 4xx over — A1 Routes should
            # not retry a webhook this app has no matching record for.
            return Response({"status": "ignored"}, status=status.HTTP_200_OK)
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class InboundEmailWebhookView(APIView):
    """``POST /api/v1/webhooks/inbound-email/`` — a customer's REPLY,
    delivered by the mail provider that owns ``INBOUND_EMAIL_DOMAIN``.

    Same trust model as the two provider webhooks below/above it:
    unauthenticated by JWT, authenticated by an HMAC signature over the
    raw body (``X-Inbound-Email-Signature``, keyed by
    ``INBOUND_EMAIL_WEBHOOK_SECRET``), verified BEFORE any database
    access, and fail-closed when the secret is unset.

    Two additional rules specific to inbound mail:

    - The conversation is identified ONLY by the CRM's own Reply-To token
      in the delivered-to address. Any ``lead_id``/``customer_id`` an
      external sender includes in the payload is ignored outright — a
      webhook body is attacker-controlled input, so trusting an id from
      it would let anyone attach a fabricated "customer reply" to any
      lead they can guess the id of.
    - The stored body is sanitized (`services.sanitize_inbound_body()`):
      mail headers dropped and bare addresses redacted, because the raw
      reply WILL contain the customer's own address and the stored body
      is employee-visible.

    Never echoes the provider payload back: the response is a fixed
    ``{"status": ...}``, so this endpoint cannot be used as a reflector to
    read back what was submitted.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "expensive_operation"

    @extend_schema(request=None, responses={200: dict, 401: dict})
    def post(self, request, *args, **kwargs):
        signature = request.headers.get("X-Inbound-Email-Signature", "")
        if not verify_inbound_email_signature(request.body, signature):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            payload = request.data if isinstance(request.data, dict) else {}
        except (AttributeError, TypeError, ParseError):
            return Response({"status": "ignored"}, status=status.HTTP_200_OK)

        message = record_inbound_email(payload)
        if message is None:
            return Response({"status": "ignored"}, status=status.HTTP_200_OK)
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class WhatsAppWebhookView(APIView):
    """``POST /api/v1/webhooks/whatsapp/`` — WhatsApp Cloud API's
    message-status callback. ``GET`` handles Meta's own webhook-
    subscription verification handshake (``hub.challenge``/
    ``hub.verify_token``) — see ``providers.whatsapp.verify_webhook_subscription_token()``.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "expensive_operation"

    @extend_schema(request=None, responses={200: dict, 403: dict})
    def get(self, request, *args, **kwargs):
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge", "")
        if mode == "subscribe" and verify_webhook_subscription_token(token):
            return Response(int(challenge) if challenge.isdigit() else challenge, status=status.HTTP_200_OK)
        return Response({"detail": "Verification failed."}, status=status.HTTP_403_FORBIDDEN)

    @extend_schema(request=None, responses={200: dict, 401: dict})
    def post(self, request, *args, **kwargs):
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_whatsapp_signature(request.body, signature):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

        # Meta's payload nests BOTH kinds of event under
        # entry[].changes[].value: delivery/read receipts for messages WE
        # sent under `statuses[]`, and the customer's own inbound replies
        # under `messages[]`. Both are audit-trail facts, so both are
        # processed here — the provider webhook is the authoritative
        # source for each (see the spec's "do not rely on the frontend to
        # create audit records").
        try:
            entries = request.data.get("entry", [])
            for entry in entries:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    for status_update in value.get("statuses", []):
                        apply_whatsapp_webhook_event(status_update)
                    receiver = str(value.get("metadata", {}).get("phone_number_id") or "")
                    for inbound in value.get("messages", []):
                        record_inbound_whatsapp(inbound, receiver=receiver)
        except (AttributeError, TypeError):
            return Response({"status": "ignored"}, status=status.HTTP_200_OK)
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
