"""CP9: serializers for the CRM domain models.

Every serializer mixes in CP7's ``SoftDeleteTimeStampedSerializerMixin``
(``apps.core.serializers``) — the first checkpoint to use it exactly as its
own usage example anticipated — so timestamps/audit/soft-delete fields are
exposed read-only in one consistent shape without being redeclared here.

As in CP8, two kinds of serializer exist per model that has a
worth-nesting relation: a **writable** serializer (foreign keys as plain
primary keys, used for create/update) and a **read-only detail**
serializer (the same data plus nested representations, used for
list/detail *output*).
"""
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.core.serializers import (
    CONTACT_CAPABILITY_FIELDS,
    ContactCapabilityMixin,
    PiiMaskedSerializerMixin,
    ServerGeneratedFieldUniqueTogetherValidator,
    SoftDeleteTimeStampedSerializerMixin,
)

from .models import Address, ContactPerson, Customer, Lead
from .opportunities import Opportunity, OpportunityActivity, OpportunityNote


class _CrmSerializer(SoftDeleteTimeStampedSerializerMixin, serializers.ModelSerializer):
    """Shared base: every CRM serializer gets the CP7 timestamp/audit/
    soft-delete field shape without repeating it per class.
    """


# --------------------------------------------------------------------------
# ContactPerson
# --------------------------------------------------------------------------


class ContactPersonSerializer(PiiMaskedSerializerMixin, ContactCapabilityMixin, _CrmSerializer):
    """``email``/``phone`` are WRITABLE (data entry is what a CRM is for)
    but are stripped from the RESPONSE for an Employee — see
    ``apps.core.serializers.PiiMaskedSerializerMixin``. An Employee reads
    ``can_email``/``can_call``/``can_whatsapp`` instead and communicates
    through ``apps.communications``, which resolves the real address/
    number server-side and never returns it.
    """

    pii_fields = ("email", "phone")

    class Meta:
        model = ContactPerson
        fields = [
            "id", "customer", "first_name", "last_name", "designation", "email", "phone", "is_primary",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ] + CONTACT_CAPABILITY_FIELDS

    def validate(self, attrs):
        """Mirrors the DB's partial unique constraint (at most one primary
        contact per customer) with a friendly 400 instead of a raw
        ``IntegrityError`` — the constraint itself remains the actual
        source of truth/last line of defense (see ``models.py``); this is
        purely a better error message for the common case.

        Skipped entirely on CREATE (``self.instance is None``):
        ``ContactPersonViewSet.perform_create()`` routes every create
        through ``apps.crm.services.add_contact()``, which auto-demotes
        the existing primary contact before creating the new one — a
        second ``is_primary=True`` at create time is the documented,
        intended way to promote a new primary, not an error. Rejecting it
        here would make ``add_contact()``'s demote step unreachable, since
        DRF calls ``validate()`` before ``perform_create()`` ever runs.
        Still enforced on UPDATE, where no such auto-demote wrapper
        exists — a PATCH shouldn't silently steal primary status from
        another contact without an explicit swap.
        """
        if self.instance is None:
            return attrs

        is_primary = attrs.get("is_primary", self.instance.is_primary)
        customer = attrs.get("customer", self.instance.customer)

        if is_primary and customer is not None:
            existing = ContactPerson.objects.filter(customer=customer, is_primary=True).exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    {"is_primary": "This customer already has a primary contact."}
                )
        return attrs


# --------------------------------------------------------------------------
# Address
# --------------------------------------------------------------------------


class AddressSerializer(_CrmSerializer):
    class Meta:
        model = Address
        fields = [
            "id", "customer", "address_type", "line1", "line2", "city", "state", "country", "postal_code",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


# --------------------------------------------------------------------------
# Customer
# --------------------------------------------------------------------------


class CustomerSerializer(PiiMaskedSerializerMixin, ContactCapabilityMixin, _CrmSerializer):
    """See ``ContactPersonSerializer`` — identical PII rule, applied to a
    `Customer`'s own ``email``/``phone``.
    """

    pii_fields = ("email", "phone")

    class Meta:
        model = Customer
        fields = [
            "id", "organization", "name", "slug", "owner", "status", "industry", "website",
            "email", "phone", "notes", "is_active",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ] + CONTACT_CAPABILITY_FIELDS
        # required=False: the model field itself requires a non-blank
        # slug, but CustomerViewSet.perform_create() routes through
        # services.create_customer(), which auto-generates one from
        # `name` when none is supplied.
        extra_kwargs = {"slug": {"required": False, "allow_blank": True}}
        # The model's organization+slug UniqueConstraint (see models.py)
        # auto-generates a plain UniqueTogetherValidator that would
        # override the extra_kwargs above and force slug required anyway
        # — see ServerGeneratedFieldUniqueTogetherValidator's own
        # docstring (apps/core/serializers.py) for why.
        validators = [
            ServerGeneratedFieldUniqueTogetherValidator(
                queryset=Customer.objects.all(), fields=("organization", "slug"), server_generated_field="slug"
            )
        ]


class CustomerDetailSerializer(CustomerSerializer):
    """Read-only: nests the owner's safe user info, the organization's
    name, and this customer's contacts/addresses — everything a detail
    view needs in one response, without a client ever being able to write
    through any of it.
    """

    owner = UserSerializer(read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    contacts = ContactPersonSerializer(many=True, read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)

    class Meta(CustomerSerializer.Meta):
        fields = CustomerSerializer.Meta.fields + ["organization_name", "contacts", "addresses"]
        read_only_fields = fields


# --------------------------------------------------------------------------
# Lead
# --------------------------------------------------------------------------


class LeadSerializer(PiiMaskedSerializerMixin, ContactCapabilityMixin, _CrmSerializer):
    """See ``ContactPersonSerializer`` — identical PII rule, applied to a
    `Lead`'s own ``email``/``phone``.
    """

    pii_fields = ("email", "phone")

    # Conversion is a workflow action (apps.crm.services.convert_lead()),
    # not a plain field edit — read-only here even on the "writable"
    # serializer so a client can never link/unlink a customer by hand.
    converted_customer = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Lead
        fields = [
            "id", "company_name", "contact_name", "email", "phone", "source", "status", "owner",
            "converted_customer", "notes",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ] + CONTACT_CAPABILITY_FIELDS

    def validate_status(self, value):
        """``CONVERTED`` is a status a lead ARRIVES at only through
        ``apps.crm.services.convert_lead()`` (which also creates and links
        the ``Customer``) — never a status a client sets directly, since
        doing so here would leave ``converted_customer`` unset and the
        lead in an inconsistent state.
        """
        if value == Lead.Status.CONVERTED:
            raise serializers.ValidationError(
                "A lead cannot be marked CONVERTED directly — use the lead-conversion service."
            )
        return value


class LeadDetailSerializer(LeadSerializer):
    """Read-only: nests the owner's safe user info and, once converted,
    the full converted ``Customer`` — not just its ID.
    """

    owner = UserSerializer(read_only=True)
    converted_customer = CustomerSerializer(read_only=True)

    class Meta(LeadSerializer.Meta):
        read_only_fields = LeadSerializer.Meta.fields


# --------------------------------------------------------------------------
# CP11: Opportunity, OpportunityActivity, OpportunityNote
# --------------------------------------------------------------------------


class OpportunityNoteSerializer(_CrmSerializer):
    class Meta:
        model = OpportunityNote
        fields = [
            "id", "opportunity", "content",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class OpportunityActivitySerializer(_CrmSerializer):
    class Meta:
        model = OpportunityActivity
        fields = [
            "id", "opportunity", "activity_type", "subject", "notes", "occurred_at",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]


class OpportunitySerializer(_CrmSerializer):
    # Closing an opportunity (WON/LOST) is a workflow action
    # (apps.crm.services.mark_won()/mark_lost()/reopen()), not a plain
    # field edit — all three read-only here even on the "writable"
    # serializer, mirroring LeadSerializer's converted_customer, so a
    # client can never desynchronize them from `stage` by editing one
    # directly.
    is_closed = serializers.BooleanField(read_only=True)
    is_won = serializers.BooleanField(read_only=True)
    actual_close_date = serializers.DateField(read_only=True)

    class Meta:
        model = Opportunity
        fields = [
            "id", "customer", "owner", "title", "stage", "value", "probability",
            "expected_close_date", "actual_close_date", "currency", "description",
            "is_closed", "is_won",
            "created_at", "updated_at", "created_by", "updated_by", "is_deleted", "deleted_at",
        ]

    def validate_stage(self, value):
        """``WON``/``LOST`` are reached only through
        ``apps.crm.services.mark_won()``/``mark_lost()`` (which also set
        ``is_closed``/``is_won``/``actual_close_date`` together) — never a
        plain ``stage`` write, for the same reason
        ``LeadSerializer.validate_status()`` blocks a direct ``CONVERTED``
        write (CP9).
        """
        if value in (Opportunity.Stage.WON, Opportunity.Stage.LOST):
            raise serializers.ValidationError(
                "Use the mark-won/mark-lost actions to close an opportunity, not a direct stage edit."
            )
        return value


class OpportunityDetailSerializer(OpportunitySerializer):
    """Read-only: nests the owner's safe user info, the customer's name,
    and this opportunity's notes/activities — mirroring
    ``CustomerDetailSerializer``'s shape (CP9).
    """

    owner = UserSerializer(read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    notes = OpportunityNoteSerializer(many=True, read_only=True)
    activities = OpportunityActivitySerializer(many=True, read_only=True)

    class Meta(OpportunitySerializer.Meta):
        fields = OpportunitySerializer.Meta.fields + ["customer_name", "notes", "activities"]
        read_only_fields = fields


class OpportunityStageTransitionSerializer(serializers.Serializer):
    """Input-only: documents the request body for
    ``OpportunityViewSet``'s ``advance-stage`` action (``{"stage": "..."}``)
    for drf-spectacular — never used to build a model instance directly
    (``apps.crm.services.advance_stage()`` does the actual validation and
    mutation; see ``apps/crm/views.py``).
    """

    stage = serializers.ChoiceField(choices=Opportunity.Stage.choices)
