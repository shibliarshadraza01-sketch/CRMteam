"""CP7: reusable serializer mixins for the abstract models in models.py.

None of these are usable standalone (there is no concrete model to point a
``ModelSerializer`` at yet — CP7 is infrastructure only, same as CP6). They
are mixins a future domain serializer (``LeadSerializer``, ``CustomerSerializer``,
...) combines with its own ``serializers.ModelSerializer`` so every future
resource exposes timestamps/audit/soft-delete fields in the exact same
shape and with the exact same safety rules, instead of each domain app
reinventing "should ``created_by`` be writable" on its own.
"""
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

# ---------------------------------------------------------------------------
# Customer-PII masking (privacy-preserving communication architecture)
# ---------------------------------------------------------------------------


def pii_masking_required(request):
    """True when the response being built is *employee-facing* and must
    therefore never carry a customer's raw email address / phone number /
    WhatsApp number.

    The rule is deliberately fail-closed for anything that is not a
    Manager-or-above authenticated request: an anonymous request, a
    request whose user has no recognizable role, and an ordinary
    ``EMPLOYEE`` all get masked output. ``request is None`` means the
    serializer is being used *internally* (a service function, a
    management command, a unit test rendering a serializer directly) —
    not across the backend-to-employee trust boundary — so no masking is
    applied there; every API view passes ``request`` in serializer
    context (DRF's ``GenericAPIView.get_serializer_context()`` does this
    unconditionally), which is what makes this safe.
    """
    if request is None:
        return False

    from apps.accounts.models import User
    from apps.accounts.permissions import user_has_role_at_least

    return not user_has_role_at_least(getattr(request, "user", None), User.Role.MANAGER)


class PiiMaskedSerializerMixin(serializers.Serializer):
    """Removes every field named in ``pii_fields`` from the serialized
    output whenever ``pii_masking_required()`` says the reader is an
    Employee (or unauthenticated).

    Implemented in ``to_representation()`` rather than by swapping
    ``Meta.fields`` per role so it applies uniformly to EVERY code path
    that renders the serializer — list, retrieve, create/update echo,
    custom actions, and (because DRF propagates ``context`` down into
    nested serializers) any nested representation of the same model.
    """

    #: Names of output fields that carry customer PII.
    pii_fields = ()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.pii_fields and pii_masking_required(self.context.get("request")):
            for field_name in self.pii_fields:
                data.pop(field_name, None)
        return data


class ContactCapabilityMixin(serializers.Serializer):
    """Adds the read-only ``can_email``/``can_call``/``can_whatsapp``
    booleans that replace raw contact details for an Employee.

    They are emitted for EVERY role (not only Employees) so the response
    shape stays stable regardless of who is reading — a client renders a
    "Call" button off ``can_call`` and never needs the number itself.
    ``can_whatsapp`` is derived from the same stored phone number the
    WhatsApp Business integration actually dials; this project stores no
    separate WhatsApp column (see ``apps.communications.services``).
    """

    can_email = serializers.SerializerMethodField()
    can_call = serializers.SerializerMethodField()
    can_whatsapp = serializers.SerializerMethodField()

    #: Model attribute holding the email address / phone number.
    email_source_field = "email"
    phone_source_field = "phone"

    @staticmethod
    def _has_value(instance, field_name):
        return bool((getattr(instance, field_name, "") or "").strip())

    def get_can_email(self, obj) -> bool:
        return self._has_value(obj, self.email_source_field)

    def get_can_call(self, obj) -> bool:
        return self._has_value(obj, self.phone_source_field)

    def get_can_whatsapp(self, obj) -> bool:
        return self._has_value(obj, self.phone_source_field)


#: Field names appended to a contact-bearing serializer's ``Meta.fields``.
CONTACT_CAPABILITY_FIELDS = ["can_email", "can_call", "can_whatsapp"]


class TimeStampedSerializerMixin(serializers.Serializer):
    """Adds read-only ``created_at``/``updated_at``.

    Always read-only: a client can never set or edit either timestamp
    directly — both are server-managed (``auto_now_add``/``auto_now`` on
    ``TimeStampedModel``). A future concrete serializer's ``Meta.fields``
    still has to list ``"created_at"``/``"updated_at"`` for them to actually
    appear in output (mixing this in only defines *how* those fields
    behave, not that they're included) — see the usage example in
    BACKEND_LEARNING_GUIDE.md CP7.
    """

    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class AuditSerializerMixin(serializers.Serializer):
    """Adds read-only ``created_by``/``updated_by`` (as plain user IDs).

    Read-only for the same reason as the timestamps above: which user
    created/last-updated a record is derived from the request, never
    supplied by the client — see ``apps/core/utils.py``'s
    ``stamp_audit_fields()``, the intended call site for actually setting
    these. Exposed as bare primary keys (not a nested user object) to keep
    this mixin dependency-free of any particular "safe user" serializer
    shape; a concrete serializer that wants the full nested user can add its
    own ``SerializerMethodField`` alongside this mixin.
    """

    created_by = serializers.PrimaryKeyRelatedField(read_only=True)
    updated_by = serializers.PrimaryKeyRelatedField(read_only=True)


class SoftDeleteSerializerMixin(serializers.Serializer):
    """Adds read-only ``is_deleted``/``deleted_at``.

    Read-only here too: soft-deleting/restoring a record is an *action*
    (``apps/core/utils.py``'s ``soft_delete()``/``restore()``, or a future
    dedicated endpoint calling them), never a plain field edit through a
    normal update payload — allowing ``is_deleted`` to be PATCHed directly
    would let any writer bypass whatever audit/permission rules a future
    "restore" endpoint enforces (e.g. CP7's own ``CanRestoreOrHardDelete``
    permission, see ``apps/core/permissions.py``).
    """

    is_deleted = serializers.BooleanField(read_only=True)
    deleted_at = serializers.DateTimeField(read_only=True, allow_null=True)


class ServerGeneratedFieldUniqueTogetherValidator(UniqueTogetherValidator):
    """Same as DRF's stock ``UniqueTogetherValidator``, but for a
    unique-together field that a service function auto-generates when
    omitted (e.g. a slug derived from a name) rather than one the client
    is always expected to supply.

    DRF's stock validator's ``enforce_required_fields()`` unconditionally
    forces EVERY field in the tuple to be present in the input, on
    create, regardless of any ``extra_kwargs``/field-level
    ``required=False`` — a real gotcha, not a bug in this project's own
    serializers, first hit by CP13's ``PriceBookEntrySerializer``
    (product/service, a genuinely-partial constraint) and again by
    CP9/10's ``CustomerSerializer`` (organization+slug, NOT partial — both
    values are always eventually present, ``slug`` is just allowed to
    arrive via server-side auto-generation instead of the client). Skips
    ONLY the named auto-generated field's presence check; every other
    field in the tuple, and the uniqueness check itself once both values
    exist, behaves exactly like the stock validator.
    """

    def __init__(self, queryset, fields, server_generated_field, message=None):
        super().__init__(queryset, fields, message=message)
        self.server_generated_field = server_generated_field

    def __call__(self, attrs, serializer):
        if serializer.instance is None and self.server_generated_field not in attrs:
            # Nothing to check yet — the server-generated field's real
            # value doesn't exist until perform_create() runs, after
            # validation. Skip both the required-check AND the uniqueness
            # query entirely; there is genuinely nothing to validate here.
            return
        super().__call__(attrs, serializer)


class SoftDeleteTimeStampedSerializerMixin(
    TimeStampedSerializerMixin, SoftDeleteSerializerMixin, AuditSerializerMixin
):
    """Combines all three mixins above — the base most future domain
    serializers are expected to mix in, mirroring ``SoftDeleteTimeStampedModel``
    on the model side.

    Example (illustrative only — no concrete model exists yet in CP7)::

        class LeadSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
            class Meta:
                model = Lead
                fields = [
                    "id", "name", "email",
                    "created_at", "updated_at",
                    "created_by", "updated_by",
                    "is_deleted", "deleted_at",
                ]
    """
