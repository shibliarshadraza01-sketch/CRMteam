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
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.core.serializers import pii_masking_required, super_admin_only_masking_required
from apps.core.utils import stamp_audit_fields
from apps.core.views import PiiSafeSearchMixin, SoftDeleteAuditModelViewSetMixin

from .filters import (
    AddressFilterSet,
    ContactPersonFilterSet,
    CustomerFilterSet,
    LeadFilterSet,
    OpportunityFilterSet,
)
from .imports import export_leads_csv, export_leads_xlsx, import_leads, parse_rows_from_file, preview_leads
from .models import Address, ContactPerson, Customer, Lead
from .opportunities import Opportunity, OpportunityActivity, OpportunityNote
from .permissions import IsManager, IsOwnerOrSuperAdmin, assert_object_accessible
from .providers.google_sheets import (
    GoogleSheetsError,
    GoogleSheetsNotConfigured,
    fetch_rows as fetch_google_sheet_rows,
    provider_status as google_sheets_status,
)
from .serializers import (
    AddressSerializer,
    ContactPersonSerializer,
    CustomerDetailSerializer,
    CustomerSerializer,
    LeadAssignmentSerializer,
    GoogleSheetImportSerializer,
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
    assign_leads,
    assign_owner,
    create_customer,
    create_opportunity,
    find_duplicate_leads,
    mark_lost,
    mark_won,
    merge_leads,
    reopen,
    resolve_owner_for_create,
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
        left implicit.

        ``restore``/``hard-delete`` skip ``scope_queryset_for_user()``
        entirely: those two actions are gated by CP7's
        ``CanRestoreOrHardDelete`` (Manager-or-above, role only — see its
        own docstring), not by ``IsOwnerOrSuperAdmin``'s per-object
        ownership check. Applying ownership scoping here too would make
        the object invisible to ``get_object()`` (a 404) for exactly the
        cross-team case ``CanRestoreOrHardDelete`` exists to allow, before
        that permission class ever gets a chance to authorize it — the
        queryset would silently defeat the permission class's own
        contract. Every other action keeps the ownership scope: an
        Employee, Manager, or Super Admin never sees rows outside what
        they're allowed to when browsing a list or looking up a specific
        ID directly for retrieve/update/destroy.
        """
        base_manager = self.base_active_manager if self.action == "list" else self.base_manager
        queryset = base_manager.all()
        if self.action in ("restore", "hard_delete"):
            return queryset
        return scope_queryset_for_user(queryset, self.request.user, owner_field=self.owner_field)


class CustomerViewSet(PiiSafeSearchMixin, _CrmModelViewSet):
    base_manager = Customer.objects
    # NOT Customer.active_objects: CustomerQuerySet.active() deliberately
    # overrides CP7's soft-delete-only active() to ALSO require
    # is_active=True (see models.py). Using it here as base_active_manager
    # would make is_active an unfilterable dead field on the list endpoint
    # — get_queryset() below re-applies the intended "not deleted only"
    # scoping instead, so is_active stays a genuine, working filter.
    base_active_manager = Customer.objects
    serializer_class = CustomerSerializer
    filterset_class = CustomerFilterSet
    full_search_fields = ["name", "email", "phone", "website"]
    pii_search_fields = ("email", "phone")
    ordering_fields = ["name", "created_at", "updated_at", "status"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = super().get_queryset().select_related("organization", "owner")
        if self.action == "list":
            queryset = queryset.filter(is_deleted=False)
        return queryset

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
        slug = data.pop("slug", "")
        owner = data.pop("owner", None)

        customer = create_customer(organization, name, slug=slug, **data)
        assign_owner(customer, resolve_owner_for_create(self.request.user, owner))
        stamp_audit_fields(customer, self.request.user, creating=True)
        customer.save()
        serializer.instance = customer


class LeadViewSet(PiiSafeSearchMixin, _CrmModelViewSet):
    base_manager = Lead.objects
    base_active_manager = Lead.active_objects
    serializer_class = LeadSerializer
    filterset_class = LeadFilterSet
    full_search_fields = ["company_name", "contact_name", "email", "phone"]
    pii_search_fields = ("email", "phone")
    ordering_fields = [("company_name", "name"), "created_at", "updated_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("owner", "converted_customer")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return LeadDetailSerializer
        return LeadSerializer

    #: Staff-management pass: bulk data-movement actions. The spec is
    #: explicit that an Employee can never export or import — enforced here
    #: at the endpoint, not by hiding a button. Manager-or-above may use
    #: them, still limited to their own scope by ``get_queryset()``
    #: (Super Admin's is the only unrestricted scope).
    data_movement_actions = (
        "import_leads_action",
        "import_preview_action",
        "import_google_sheet_action",
        "google_sheet_status_action",
        "export_leads_action",
    )

    def get_permissions(self):
        permissions = super().get_permissions()
        if self.action in self.data_movement_actions:
            permissions = permissions + [IsManager()]
        return permissions

    def get_throttles(self):
        # Rate-limited: merge/import/export are all real, comparatively
        # expensive bulk operations — see config/settings/base.py's
        # "expensive_operation" scope docstring. Ordinary list/create/
        # retrieve/duplicates on this viewset are unaffected.
        if self.action in (
            "merge",
            "import_leads_action",
            "export_leads_action",
            "import_preview_action",
            "import_google_sheet_action",
        ):
            self.throttle_scope = "expensive_operation"
            return [ScopedRateThrottle()]
        return super().get_throttles()

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
        resolved_owner = resolve_owner_for_create(self.request.user, lead.owner)
        if resolved_owner.pk != lead.owner_id:
            assign_owner(lead, resolved_owner)

    @extend_schema(request=None, responses={200: LeadSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def duplicates(self, request, *args, **kwargs):
        """``GET /leads/<id>/duplicates/`` — other leads that plausibly
        refer to the same real-world contact (see
        ``services.find_duplicate_leads()``), scoped by the same
        ownership rule as every other list result on this viewset.
        """
        lead = self.get_object()
        queryset = scope_queryset_for_user(find_duplicate_leads(lead), request.user, owner_field=self.owner_field)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(request=None, responses={200: LeadSerializer})
    @action(detail=True, methods=["post"], url_path="merge")
    def merge(self, request, *args, **kwargs):
        """``POST /leads/<id>/merge/`` — merge ``duplicate_id`` (body) into
        this lead (see ``services.merge_leads()``). Both leads must
        actually be visible to the requester under the normal ownership
        rule — this action does not grant any additional reach.
        """
        primary = self.get_object()
        duplicate_id = request.data.get("duplicate_id")
        if not duplicate_id:
            return Response({"detail": "duplicate_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        visible = scope_queryset_for_user(self.base_manager.all(), request.user, owner_field=self.owner_field)
        duplicate = get_object_or_404(visible, pk=duplicate_id)

        try:
            merge_leads(primary, duplicate, merged_by=request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        primary.refresh_from_db()
        serializer = self.get_serializer(primary)
        return Response(serializer.data)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=False, methods=["post"], url_path="import")
    def import_leads_action(self, request, *args, **kwargs):
        """``POST /leads/import/`` — bulk-create leads from an uploaded
        ``.csv``/``.xlsx`` file (multipart field name ``file``). Every
        row is validated independently (see ``imports.import_leads()``):
        malformed rows are reported, not silently dropped or allowed to
        abort the whole file. Imported leads default to the requester as
        owner, exactly like a single manual create.
        """
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response({"detail": "A file is required (multipart field 'file')."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rows = parse_rows_from_file(uploaded_file)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        summary = import_leads(rows, default_owner=request.user, created_by=request.user)
        return Response(summary, status=status.HTTP_200_OK)

    @extend_schema(request=LeadAssignmentSerializer, responses={200: LeadSerializer(many=True)})
    @action(detail=False, methods=["post"], url_path="assign")
    def assign(self, request, *args, **kwargs):
        """``POST /leads/assign/`` — bulk (re)assign leads.

        Body::

            {"lead_ids": [1, 2], "target_type": "manager"|"employee",
             "target_user_id": 7}

        Authorization is entirely ``services.assign_leads()``'s (see its
        docstring): Super Admin may assign any visible lead to any
        Manager/Employee; a Manager may assign only leads already in
        their own scope, and only to themselves or someone in their own
        ``managed_user_ids()``; an Employee is always refused (403).
        Unknown/out-of-scope lead ids return 404 rather than being
        silently skipped.

        Returns the updated leads, serialized exactly like ``list`` (so
        ``source`` is still stripped for a Manager — assignment does not
        widen anyone's field visibility).
        """
        serializer = LeadAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.accounts.models import User as UserModel

        target_user = UserModel.objects.filter(pk=data["target_user_id"]).first()
        try:
            leads = assign_leads(request.user, data["lead_ids"], data["target_type"], target_user)
        except Lead.DoesNotExist as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

        return Response(self.get_serializer(leads, many=True).data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=False, methods=["post"], url_path="import-preview")
    def import_preview_action(self, request, *args, **kwargs):
        """``POST /leads/import-preview/`` — the PREVIEW stage of the
        import workflow (multipart field ``file``, same formats as
        ``import``). Validates every row and returns what WOULD be
        created; writes nothing. See ``imports.preview_leads()``.
        """
        uploaded_file = request.FILES.get("file")
        if uploaded_file is None:
            return Response(
                {"detail": "A file is required (multipart field 'file')."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            rows = parse_rows_from_file(uploaded_file)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(preview_leads(rows), status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: dict})
    @action(detail=False, methods=["get"], url_path="google-sheet-status")
    def google_sheet_status_action(self, request, *args, **kwargs):
        """``GET /leads/google-sheet-status/`` — whether a Google Sheets
        import can currently run on this deployment. Never returns any
        credential value; safe to call with nothing configured (that is
        exactly what it reports).
        """
        return Response(google_sheets_status(), status=status.HTTP_200_OK)

    @extend_schema(request=GoogleSheetImportSerializer, responses={200: dict})
    @action(detail=False, methods=["post"], url_path="import-google-sheet")
    def import_google_sheet_action(self, request, *args, **kwargs):
        """``POST /leads/import-google-sheet/`` — the full
        source -> adapter -> validation -> preview -> confirm pipeline for
        a Google-Sheets-sourced lead import.

        Body: ``{"spreadsheet_id": "...", "sheet_range": "Sheet1!A:G",
        "confirm": false}``. ``confirm=false`` (default) returns the same
        preview payload as ``import-preview``; ``confirm=true`` runs the
        SAME ``imports.import_leads()`` pipeline the file upload uses —
        one import path, two sources, no parallel implementation.

        If Google Sheets credentials are absent this returns **503 with
        ``"configured": false``** — never a fabricated success. Nothing
        about this endpoint (or its module import) affects startup.
        """
        serializer = GoogleSheetImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            rows = fetch_google_sheet_rows(data["spreadsheet_id"], data.get("sheet_range") or None)
        except GoogleSheetsNotConfigured as exc:
            return Response(
                {"detail": str(exc), "configured": False, **google_sheets_status()},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except GoogleSheetsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        if not data.get("confirm"):
            return Response(
                {"stage": "preview", "source": "google_sheets", **preview_leads(rows)},
                status=status.HTTP_200_OK,
            )

        summary = import_leads(rows, default_owner=request.user, created_by=request.user)
        return Response(
            {"stage": "imported", "source": "google_sheets", **summary}, status=status.HTTP_200_OK
        )

    @extend_schema(request=None, responses={200: bytes})
    @action(detail=False, methods=["get"], url_path="export")
    def export_leads_action(self, request, *args, **kwargs):
        """``GET /leads/export/?export_format=csv|xlsx`` — every lead the
        requester can see (the same ownership scoping and filters
        ``list`` applies), as a downloadable file. Defaults to CSV.

        NOTE: the query parameter is deliberately NOT named ``format`` —
        that name is reserved by DRF's own content-negotiation (
        ``URL_FORMAT_OVERRIDE``, default ``"format"``) and colliding with
        it makes DRF try to resolve a renderer named "xlsx", which
        doesn't exist, producing a 404 before this method ever runs.
        """
        export_format = request.query_params.get("export_format", "csv").lower()
        if export_format not in ("csv", "xlsx"):
            return Response({"detail": "export_format must be 'csv' or 'xlsx'."}, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.filter_queryset(self.get_queryset())

        # An export is just another response body: the same PII rule the
        # JSON API enforces applies to the downloadable file, so an
        # Employee's export omits the lead email/phone columns entirely
        # rather than handing over in a spreadsheet what the API refuses
        # to return in JSON.
        include_pii = not pii_masking_required(request)
        # Lead Source is Super-Admin-only (see LeadSerializer's
        # super_admin_only_fields). An export is just another response
        # body, so a Manager's/Employee's download must not carry the
        # column the JSON API strips for them.
        include_source = not super_admin_only_masking_required(request)

        if export_format == "xlsx":
            content = export_leads_xlsx(queryset, include_pii=include_pii, include_source=include_source)
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "leads.xlsx"
        else:
            content = export_leads_csv(queryset, include_pii=include_pii, include_source=include_source)
            content_type = "text/csv"
            filename = "leads.csv"

        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ContactPersonViewSet(PiiSafeSearchMixin, _CrmModelViewSet):
    base_manager = ContactPerson.objects
    base_active_manager = ContactPerson.active_objects
    serializer_class = ContactPersonSerializer
    filterset_class = ContactPersonFilterSet
    full_search_fields = ["first_name", "last_name", "email"]
    pii_search_fields = ("email",)
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
        assert_object_accessible(self.request, customer)
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
        assert_object_accessible(self.request, customer)
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
        assign_owner(opportunity, resolve_owner_for_create(self.request.user, owner))
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
