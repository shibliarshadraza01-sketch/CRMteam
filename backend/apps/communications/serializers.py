"""CP15: serializers for the communications domain.

Every serializer mixes in CP7's `SoftDeleteTimeStampedSerializerMixin`.
`EmailMessage`/`Notification` reuse CP14's `RelatedObjectMixin`
(`apps.activities.serializers`) UNCHANGED for the same read-only
`related_object` summary shape `Task`/`Event`/`ActivityLog` already
expose — imported, not re-implemented.
"""
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from apps.activities.serializers import RelatedObjectMixin
from apps.core.serializers import PiiMaskedSerializerMixin, SoftDeleteTimeStampedSerializerMixin
from apps.crm.models import ContactPerson, Customer, Lead

from .models import Call, CommunicationLog, EmailMessage, EmailTemplate, Notification


class _CommunicationsSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base: every communications serializer gets the CP7
    timestamp/audit/soft-delete field shape without repeating it per class.
    """


class EmailTemplateSerializer(_CommunicationsSerializer):
    class Meta:
        model = EmailTemplate
        fields = [
            "id", "name", "subject", "body", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class EmailMessageSerializer(PiiMaskedSerializerMixin, RelatedObjectMixin, _CommunicationsSerializer):
    """``to_email`` is the customer's REAL address and is stripped from the
    response for an Employee (`PiiMaskedSerializerMixin`); a Manager/Super
    Admin still sees it, exactly as they can on the `Customer` record
    itself. Every reader — including an Employee — gets
    ``recipient_label``, a safe description of WHO the message went to
    (the related customer/lead), which is what a UI actually needs to
    render a sent-mail list.
    """

    pii_fields = ("to_email",)

    recipient_label = serializers.SerializerMethodField()

    class Meta:
        model = EmailMessage
        fields = [
            "id", "template", "owner", "to_email", "recipient_label", "subject", "body",
            "status", "direction", "sent_at", "error_message", "in_reply_to",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = [
            # ``to_email`` is READ-ONLY as well as masked. It is resolved
            # once, at queue time, from the related contact; leaving it
            # PATCHable would let an Employee re-point an already-queued
            # message at an arbitrary address and then POST .../send/ —
            # i.e. turn this resource into the open relay the create
            # endpoint deliberately refuses to be.
            "to_email",
            "subject", "body", "status", "direction", "sent_at", "error_message", "in_reply_to",
        ]

    def get_recipient_label(self, obj) -> str:
        """Who this email went to, WITHOUT the address: the related
        customer/lead's own display name when the message is attached to
        one, else a neutral placeholder. Never derived from ``to_email``.
        """
        if obj.content_type_id and obj.object_id:
            target = obj.related_object
            if target is not None:
                return str(target)
        return "(recipient hidden)"


class EmailMessageQueueSerializer(serializers.Serializer):
    """Write-only input shape for `EmailMessageViewSet.create()` — NOT a
    `ModelSerializer`: queueing an email is `services.queue_email()`'s
    "either a template+context, or an explicit subject+body" union, which
    doesn't map onto a single flat set of model fields the way ordinary
    creation does (see `views.py`'s `perform_create()`).

    THE RECIPIENT IS AN ENTITY, NOT AN ADDRESS. A caller names the
    ``customer``/``lead``/``contact`` (or the generic
    ``content_type``+``object_id`` pair this app already used to attach a
    message to an entity) and the backend resolves the real address
    itself. The old required ``to_email`` input is gone for customer mail:
    accepting it would both require the employee to already hold the
    address AND turn this endpoint into an open relay to any address an
    authenticated user cares to type.

    ``to_email`` survives for exactly ONE documented case: self-addressed
    mail (e.g. the payment-reminder digest an employee sends to their own
    signed-in address). `views.py` enforces that restriction — an address
    that is not the requester's own is rejected unless the requester is a
    Manager/Super Admin, who can already read customer addresses anyway.
    """

    to_email = serializers.EmailField(
        required=False,
        help_text=(
            "Self-addressed mail only (must equal the requesting user's own address) unless the "
            "requester is a Manager/Super Admin. To email a customer/lead, pass `customer`, `lead`, "
            "`contact`, or content_type+object_id."
        ),
    )
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False)
    lead = serializers.PrimaryKeyRelatedField(queryset=Lead.objects.all(), required=False)
    contact = serializers.PrimaryKeyRelatedField(queryset=ContactPerson.objects.all(), required=False)
    template = serializers.PrimaryKeyRelatedField(queryset=EmailTemplate.active_objects.all(), required=False)
    context = serializers.DictField(required=False)
    subject = serializers.CharField(required=False, allow_blank=False)
    body = serializers.CharField(required=False, allow_blank=False)
    content_type = serializers.PrimaryKeyRelatedField(queryset=ContentType.objects.all(), required=False)
    object_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        """Mirrors `services.queue_email()`'s own "template XOR subject+body"
        rule with a friendlier 400 — same three-layer pattern (service +
        serializer) CP13/CP14 established, minus the DB constraint layer
        (queueing has no DB-enforceable invariant to mirror here, unlike
        `PriceBookEntry`/`Reminder`'s exactly-one-of constraints) — plus a
        "there must be SOME resolvable recipient" check.
        """
        has_template = bool(attrs.get("template"))
        has_subject_and_body = bool(attrs.get("subject")) and bool(attrs.get("body"))
        if has_template == has_subject_and_body:
            raise serializers.ValidationError(
                "Provide either `template` (+ optional `context`), or both `subject` and `body`, not both forms."
            )

        named_targets = [attrs.get("customer"), attrs.get("lead"), attrs.get("contact")]
        supplied = [target for target in named_targets if target is not None]
        if len(supplied) > 1:
            raise serializers.ValidationError("Provide at most one of `customer`, `lead` or `contact`.")

        has_generic_target = attrs.get("content_type") is not None and attrs.get("object_id") is not None
        if not supplied and not has_generic_target and not attrs.get("to_email"):
            raise serializers.ValidationError(
                "Provide a recipient: `customer`, `lead`, `contact`, content_type+object_id, "
                "or `to_email` for self-addressed mail."
            )
        return attrs


class NotificationSerializer(RelatedObjectMixin, _CommunicationsSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "recipient", "notification_type", "title", "message", "is_read", "read_at",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = ["is_read", "read_at"]


class CommunicationLogSerializer(RelatedObjectMixin, _CommunicationsSerializer):
    """Entirely read-only — see `models.py`'s `CommunicationLog` docstring
    and `views.py`: there is no create endpoint, only list/retrieve.
    """

    class Meta:
        model = CommunicationLog
        fields = [
            "id", "channel", "actor", "summary", "occurred_at",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = fields


# --------------------------------------------------------------------------
# Call (A1 Routes SIP)
# --------------------------------------------------------------------------


class CallSerializer(PiiMaskedSerializerMixin, RelatedObjectMixin, _CommunicationsSerializer):
    """Read-only status/timing fields — a call's lifecycle is driven
    entirely by ``services.initiate_call()`` and the A1 Routes webhook
    (``apps.communications.services.apply_a1routes_webhook_event()``),
    never by a plain PATCH — the same "no supported way to reach a new
    status through a plain PATCH" rule CP12's ``InvoiceSerializer``
    already applies to its own workflow-only fields.
    """

    #: The customer's real number (``to_number``) and the CRM's own trunk
    #: number (``from_number``) are both stripped for an Employee: the
    #: first is customer PII, the second is infrastructure detail an
    #: employee's browser has no reason to hold. Everything an employee
    #: actually needs — who was called, when, how long, what happened —
    #: stays.
    pii_fields = ("from_number", "to_number")

    class Meta:
        model = Call
        fields = [
            "id", "owner", "direction", "from_number", "to_number", "provider_call_id",
            "status", "started_at", "ended_at", "duration_seconds", "error_message",
            "content_type", "object_id", "related_object",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]
        read_only_fields = [
            "direction", "from_number", "to_number", "provider_call_id", "status",
            "started_at", "ended_at", "duration_seconds", "error_message",
        ]


class InitiateCallSerializer(serializers.Serializer):
    """Write-only input shape for ``CallViewSet.create()`` — see
    ``EmailMessageQueueSerializer``'s own docstring for why an initiate-
    style action is a plain ``Serializer``, not a ``ModelSerializer``:
    the client supplies only what it can know (WHO to call), never the
    provider-assigned fields — and, now, never the number either.

    ``to_number`` is gone entirely. There is no legitimate flow in which
    an employee's browser needs to name the number to dial: it names the
    customer/lead, and ``services.initiate_call()`` resolves the number
    from the database.
    """

    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False)
    lead = serializers.PrimaryKeyRelatedField(queryset=Lead.objects.all(), required=False)
    contact = serializers.PrimaryKeyRelatedField(queryset=ContactPerson.objects.all(), required=False)
    content_type = serializers.PrimaryKeyRelatedField(queryset=ContentType.objects.all(), required=False)
    object_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        named_targets = [attrs.get("customer"), attrs.get("lead"), attrs.get("contact")]
        supplied = [target for target in named_targets if target is not None]
        if len(supplied) > 1:
            raise serializers.ValidationError("Provide at most one of `customer`, `lead` or `contact`.")

        has_generic_target = attrs.get("content_type") is not None and attrs.get("object_id") is not None
        if not supplied and not has_generic_target:
            raise serializers.ValidationError(
                "Provide who to call: `customer`, `lead`, `contact`, or content_type+object_id."
            )
        return attrs
