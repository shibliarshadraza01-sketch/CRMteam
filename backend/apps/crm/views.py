"""CP10: the CRM domain's REST API.

Every viewset here is built entirely from existing infrastructure — CP7's
``SoftDeleteAuditModelViewSetMixin`` (soft-delete-on-DELETE, audit
stamping, ``restore``/``hard-delete`` actions — defined in CP7 but never
before wired to a real endpoint), CP9's serializers, and CP6's/CP9's
permission classes. No permission-checking or soft-delete logic is
reimplemented here — see each viewset's ``perform_create()`` for where
business logic is deliberately routed through ``apps/crm/services.py``
instead of being inlined.

Access shape (all four resources): any authenticated user may list/create
(results/effect scoped by ownership — see ``get_queryset()``); retrieving,
updating, or deleting a SPECIFIC object requires being its owner (directly,
or via ``Customer``/``Lead.manager_has_access()`` for a Manager overseeing
the owner's team), or being a Super Admin — enforced by CP6's
``IsOwnerOrSuperAdmin``, unchanged.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.utils import stamp_audit_fields
from apps.core.views import SoftDeleteAuditModelViewSetMixin

from .filters import (
    AddressFilterSet,
    ContactPersonFilterSet,
    CustomerFilterSet,
    LeadFilterSet,
    OpportunityFilterSet,
)
from .models import Address, ContactPerson, Customer, Lead
from .opportunities import Opportunity, OpportunityActivity, OpportunityNote
from .permissions import IsOwnerOrSuperAdmin
from .serializers import (
    AddressSerializer,
    ContactPersonSerializer,
    CustomerDetailSerializer,
    CustomerSerializer,
    LeadDetailSerializer,
    LeadSerializer,
    OpportunityActivitySerializer,
    OpportunityDetailSerializer,
    OpportunityNoteSerializer,
    OpportunitySerializer,
    OpportunityStageTransitionSerializer,
)
from .services import (
    add_activity,
    add_address,
    add_contact,
    add_note,
    advance_stage,
    assign_owner,
    create_customer,
    create_opportunity,
    mark_lost,
    mark_won,
    reopen,
    scope_queryset_for_user,
)


class _CrmModelViewSet(SoftDeleteAuditModelViewSetMixin, viewsets.ModelViewSet):
    """Shared base for every CP10 viewset.

    - No ``PUT`` (full update) — only ``PATCH`` (partial update), per CP10's
      endpoint spec, which lists PATCH but never PUT for any resource.
    - ``IsOwnerOrSuperAdmin`` (CP6) is the only permission class beyond
      ``IsAuthenticated`` — its ``has_permission()`` only requires
      authentication (list/create are gated by ``get_queryset()`` scoping,
      not by a role check), and its ``has_object_permission()`` is the
      actual "owner, their manager, or Super Admin" gate for
      retrieve/update/destroy/restore/hard-delete.
    """

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated, IsOwnerOrSuperAdmin]

    #: ORM path from this viewset's model to the ``User`` that owns each
    #: row — see ``services.scope_queryset_for_user()``'s docstring.
    owner_field = "owner"

    def get_queryset(self):
        """List results are scoped to *active* (not soft-deleted) rows;
        every other action (retrieve/update/destroy/restore/hard-delete)
        deliberately uses the UNFILTERED manager so a soft-deleted row
        remains reachable for ``restore``/``hard-delete`` — see CP7's
        ``SoftDeleteModelMixin.restore()`` docstring for why this can't be
        left implicit. Both branches are then scoped by ownership via
        ``scope_queryset_for_user()`` (CP10) — an Employee, Manager, or
        Super Admin never sees rows outside what they're allowed to,
        whether browsing a list or looking up a specific ID directly.
        """
        base_manager = self.base_active_manager if self.action == "list" else self.base_manager
        queryset = base_manager.all()
        return scope_queryset_for_user(queryset, self.request.user, owner_field=self.owner_field)


class CustomerViewSet(_CrmModelViewSet):
    base_manager = Customer.objects
    base_active_manager = Customer.active_objects
    serializer_class = CustomerSerializer
    filterset_class = CustomerFilterSet
    search_fields = ["name", "email", "phone", "website"]
    ordering_fields = ["name", "created_at", "updated_at", "status"]
    ordering = ["name"]

    def get_queryset(self):
        return super().get_queryset().select_related("organization", "owner")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return CustomerDetailSerializer
        return CustomerSerializer

    def perform_create(self, serializer):
        """Routes creation through CP9's ``create_customer()`` (real
        behavior: ``slug`` auto-generation from ``name`` when blank) and
        ``assign_owner()`` (defaults ``owner`` to the requesting user when
        not explicitly supplied — the "Employees own their own records"
        rule starts here, at creation time) rather than a bare
        ``serializer.save()``.
        """
        data = dict(serializer.validated_data)
        organization = data.pop("organization")
        name = data.pop("name")
        slug = data.pop("slug")
        owner = data.pop("owner", None)

        customer = create_customer(organization, name, slug=slug, **data)
        assign_owner(customer, owner or self.request.user)
        stamp_audit_fields(customer, self.request.user, creating=True)
        customer.save()
        serializer.instance = customer


class LeadViewSet(_CrmModelViewSet):
    base_manager = Lead.objects
    base_active_manager = Lead.active_objects
    serializer_class = LeadSerializer
    filterset_class = LeadFilterSet
    search_fields = ["company_name", "contact_name", "email", "phone"]
    ordering_fields = [("company_name", "name"), "created_at", "updated_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("owner", "converted_customer")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return LeadDetailSerializer
        return LeadSerializer

    def perform_create(self, serializer):
        """Standard audit-stamped creation (CP7's ``AuditStampedModelMixin``
        — no CP9 service has real behavior beyond a bare ``.create()`` for
        a `Lead`, see ``services.create_lead()``'s own docstring), plus
        defaulting ``owner`` to the requesting user via ``assign_owner()``
        when not explicitly supplied — the same "Employees own their own
        records" rule ``CustomerViewSet`` applies.
        """
        super().perform_create(serializer)
        lead = serializer.instance
        if lead.owner_id is None:
            assign_owner(lead, self.request.user)


class ContactPersonViewSet(_CrmModelViewSet):
    base_manager = ContactPerson.objects
    base_active_manager = ContactPerson.active_objects
    serializer_class = ContactPersonSerializer
    filterset_class = ContactPersonFilterSet
    search_fields = ["first_name", "last_name", "email"]
    ordering_fields = [("last_name", "name"), "created_at", "updated_at"]
    ordering = ["-is_primary", "last_name"]
    owner_field = "customer__owner"

    def get_queryset(self):
        return super().get_queryset().select_related("customer", "customer__owner")

    def perform_create(self, serializer):
        """Routes creation through CP9's ``add_contact()`` — real behavior:
        demotes an existing primary contact before promoting a new one,
        rather than relying on the client to sequence two separate calls.
        """
        data = dict(serializer.validated_data)
        customer = data.pop("customer")
        first_name = data.pop("first_name")
        last_name = data.pop("last_name")
        is_primary = data.pop("is_primary", False)

        contact = add_contact(customer, first_name, last_name, is_primary=is_primary, **data)
        stamp_audit_fields(contact, self.request.user, creating=True)
        contact.save()
        serializer.instance = contact


class AddressViewSet(_CrmModelViewSet):
    base_manager = Address.objects
    base_active_manager = Address.active_objects
    serializer_class = AddressSerializer
    filterset_class = AddressFilterSet
    search_fields = ["line1", "city", "postal_code"]
    ordering_fields = ["created_at", "updated_at", "city"]
    ordering = ["customer", "address_type"]
    owner_field = "customer__owner"

    def get_queryset(self):
        return super().get_queryset().select_related("customer", "customer__owner")

    def perform_create(self, serializer):
        """Routes creation through CP9's ``add_address()`` for architectural
        symmetry with ``ContactPersonViewSet`` — today a thin wrapper (see
        that function's own docstring), kept as the single seam a future
        address-specific rule would be added to.
        """
        data = dict(serializer.validated_data)
        customer = data.pop("customer")
        address_type = data.pop("address_type")

        address = add_address(customer, address_type, **data)
        stamp_audit_fields(address, self.request.user, creating=True)
        address.save()
        serializer.instance = address


class OpportunityViewSet(_CrmModelViewSet):
    """CP11: the sales pipeline API. Standard CRUD (list/create/retrieve/
    patch/delete — via ``_CrmModelViewSet``) plus four custom actions
    covering the stage machine (``advance-stage``, ``mark-won``,
    ``mark-lost``, ``reopen`` — each a thin wrapper around the matching
    ``apps/crm/services.py`` function, so the actual business rules
    ("cannot move past WON/LOST unless reopened", what WON/LOST/reopen()
    each set) live in exactly one place, not duplicated here) and two
    nested list+create actions (``notes``, ``activities``).

    No new permission logic: every action here — including the four
    stage-transition actions and the two nested resource actions — is
    reached via ``self.get_object()``, which runs the SAME
    ``IsOwnerOrSuperAdmin`` object-level check (CP6) as ordinary retrieve/
    update/destroy, through the class-level ``permission_classes``
    inherited from ``_CrmModelViewSet``. No action here declares its own
    ``permission_classes`` override.
    """

    base_manager = Opportunity.objects
    base_active_manager = Opportunity.active_objects
    serializer_class = OpportunitySerializer
    filterset_class = OpportunityFilterSet
    search_fields = ["title", "customer__name", "description"]
    ordering_fields = ["title", "value", "probability", "expected_close_date", "created_at", "updated_at", "stage"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("customer", "owner")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return OpportunityDetailSerializer
        return OpportunitySerializer

    def perform_create(self, serializer):
        """Routes creation through CP11's ``create_opportunity()`` +
        CP9/CP10's ``assign_owner()`` — the same "default owner to the
        requesting user when not supplied" rule ``CustomerViewSet``/
        ``LeadViewSet`` already apply.
        """
        data = dict(serializer.validated_data)
        customer = data.pop("customer")
        title = data.pop("title")
        owner = data.pop("owner", None)

        opportunity = create_opportunity(customer, title, **data)
        assign_owner(opportunity, owner or self.request.user)
        stamp_audit_fields(opportunity, self.request.user, creating=True)
        opportunity.save()
        serializer.instance = opportunity

    def _stage_transition_response(self, opportunity):
        serializer = self.get_serializer(opportunity)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=OpportunityStageTransitionSerializer, responses={200: OpportunitySerializer})
    @action(detail=True, methods=["post"], url_path="advance-stage")
    def advance_stage(self, request, *args, **kwargs):
        """``POST /opportunities/<id>/advance-stage/`` — ``{"stage": "..."}``.
        Rejects WON/LOST (use ``mark-won``/``mark-lost``) and rejects any
        change on an already-closed opportunity (use ``reopen`` first) —
        both enforced by ``services.advance_stage()``, not here.
        """
        serializer = OpportunityStageTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        opportunity = self.get_object()
        try:
            advance_stage(opportunity, serializer.validated_data["stage"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._stage_transition_response(opportunity)

    @extend_schema(request=None, responses={200: OpportunitySerializer})
    @action(detail=True, methods=["post"], url_path="mark-won")
    def mark_won(self, request, *args, **kwargs):
        """``POST /opportunities/<id>/mark-won/`` — closes the opportunity
        as won; sets ``is_closed``/``is_won``/``actual_close_date``
        together (``services.mark_won()``).
        """
        opportunity = self.get_object()
        try:
            mark_won(opportunity)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._stage_transition_response(opportunity)

    @extend_schema(request=None, responses={200: OpportunitySerializer})
    @action(detail=True, methods=["post"], url_path="mark-lost")
    def mark_lost(self, request, *args, **kwargs):
        """``POST /opportunities/<id>/mark-lost/`` — the LOST counterpart
        to ``mark-won`` (``services.mark_lost()``).
        """
        opportunity = self.get_object()
        try:
            mark_lost(opportunity)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._stage_transition_response(opportunity)

    @extend_schema(request=None, responses={200: OpportunitySerializer})
    @action(detail=True, methods=["post"])
    def reopen(self, request, *args, **kwargs):
        """``POST /opportunities/<id>/reopen/`` — reverses ``mark-won``/
        ``mark-lost``, clearing ``is_closed``/``is_won``/
        ``actual_close_date`` and returning the opportunity to ``NEW``
        (``services.reopen()``).
        """
        opportunity = self.get_object()
        try:
            reopen(opportunity)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._stage_transition_response(opportunity)

    @extend_schema(
        methods=["GET"], responses={200: OpportunityNoteSerializer(many=True)},
    )
    @extend_schema(
        methods=["POST"], request=OpportunityNoteSerializer, responses={201: OpportunityNoteSerializer},
    )
    @action(detail=True, methods=["get", "post"])
    def notes(self, request, *args, **kwargs):
        """``GET``/``POST /opportunities/<id>/notes/`` — the opportunity's
        notes. ``POST`` routes through ``services.add_note()``, stamping
        ``created_by`` from the requesting user.
        """
        opportunity = self.get_object()
        if request.method == "POST":
            note = add_note(opportunity, request.data.get("content", ""), created_by=request.user)
            serializer = OpportunityNoteSerializer(note)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        queryset = OpportunityNote.active_objects.filter(opportunity=opportunity)
        serializer = OpportunityNoteSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(
        methods=["GET"], responses={200: OpportunityActivitySerializer(many=True)},
    )
    @extend_schema(
        methods=["POST"], request=OpportunityActivitySerializer, responses={201: OpportunityActivitySerializer},
    )
    @action(detail=True, methods=["get", "post"])
    def activities(self, request, *args, **kwargs):
        """``GET``/``POST /opportunities/<id>/activities/`` — the
        opportunity's logged activities. ``POST`` routes through
        ``services.add_activity()``, stamping ``created_by`` from the
        requesting user.
        """
        opportunity = self.get_object()
        if request.method == "POST":
            activity = add_activity(
                opportunity,
                request.data.get("activity_type", "OTHER"),
                request.data.get("subject", ""),
                notes=request.data.get("notes", ""),
                created_by=request.user,
            )
            serializer = OpportunityActivitySerializer(activity)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        queryset = OpportunityActivity.active_objects.filter(opportunity=opportunity)
        serializer = OpportunityActivitySerializer(queryset, many=True)
        return Response(serializer.data)
