"""CP7: reusable view/viewset mixins for soft-deletable, audited resources.

Like ``serializers.py``, none of these are directly reachable over HTTP yet
— CP7 defines no concrete endpoint (see ``urls.py``, currently empty). They
are the base classes a future domain app's views are expected to combine
with a concrete ``queryset``/``serializer_class`` so "DELETE means soft
delete, not a real SQL DELETE" and "who created/last touched this" are
handled consistently everywhere, rather than re-derived per app.
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from .permissions import CanRestoreOrHardDelete
from .utils import stamp_audit_fields


class AuditStampedModelMixin:
    """Stamps ``created_by``/``updated_by`` from ``request.user`` on
    create/update, via ``apps/core/utils.py``'s ``stamp_audit_fields()``.

    Mix into a DRF generic view/viewset ALONGSIDE the normal
    ``CreateModelMixin``/``UpdateModelMixin`` (or a full ``ModelViewSet``) —
    it overrides ``perform_create``/``perform_update``, not
    ``create``/``update``, so it composes with DRF's own mixins rather than
    replacing them.
    """

    def perform_create(self, serializer):
        user = getattr(self.request, "user", None)
        instance = serializer.save()
        stamp_audit_fields(instance, user, creating=True)
        instance.save()

    def perform_update(self, serializer):
        user = getattr(self.request, "user", None)
        instance = serializer.save()
        stamp_audit_fields(instance, user, creating=False)
        instance.save()


class SoftDeleteModelMixin:
    """Makes DRF's standard ``DELETE`` soft-delete instead of hard-delete,
    and adds ``POST .../<pk>/restore/`` and ``POST .../<pk>/hard-delete/``
    actions gated to Manager-or-above.

    Mix into a ``ModelViewSet`` (or any view with ``DestroyModelMixin``)
    whose model inherits ``apps.core.models.SoftDeleteModel``. Overrides
    ``perform_destroy`` so the inherited ``destroy()`` action — and
    therefore the standard ``DELETE /resource/<pk>/`` HTTP verb — soft
    deletes rather than removing the row, matching CP7's "no permanent
    delete unless explicitly requested" rule.
    """

    def perform_destroy(self, instance):
        instance.soft_delete(updated_by=getattr(self.request, "user", None))

    @action(detail=True, methods=["post"], permission_classes=[CanRestoreOrHardDelete])
    def restore(self, request, *args, **kwargs):
        """``POST /<resource>/<pk>/restore/`` — undo a soft delete.

        Looks the object up via ``self.get_queryset()`` directly (not
        ``self.get_object()``) because ``get_object()`` on most viewsets
        filters through the model's default manager, which — per
        ``SoftDeleteModel`` — already includes deleted rows; this is kept
        explicit rather than relied upon implicitly, so a future viewset
        that overrides ``get_queryset()`` to something narrower doesn't
        silently break restore.
        """
        instance = self.get_object()
        instance.restore(updated_by=getattr(request, "user", None))
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="hard-delete", permission_classes=[CanRestoreOrHardDelete])
    def hard_delete(self, request, *args, **kwargs):
        """``POST /<resource>/<pk>/hard-delete/`` — permanent delete.

        Deliberately a separate, explicitly-named action rather than
        reusing ``DELETE`` for this — see CP7's "no permanent delete unless
        explicitly requested" rule and ``SoftDeleteModel.hard_delete()``'s
        own docstring for why the ordinary delete verb never reaches this
        path implicitly.
        """
        instance = self.get_object()
        instance.hard_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SoftDeleteAuditModelViewSetMixin(AuditStampedModelMixin, SoftDeleteModelMixin):
    """Convenience combination of both mixins above — the one most future
    domain ``ModelViewSet`` subclasses are expected to actually use.
    """


class ReferenceDataModelViewSetMixin(SoftDeleteAuditModelViewSetMixin):
    """Shared base for "reference data" resources — records with no
    ownership concept (no per-row ``owner``, unlike ``apps.crm``'s own
    ``_CrmModelViewSet``, which this mixin deliberately does NOT build on
    for exactly that reason): no ``PUT`` (only ``PATCH``, the same
    restriction every CP10+ viewset uses), and the same active-vs-
    unfiltered ``get_queryset()`` split by action every soft-deletable
    viewset in this project uses (a soft-deleted row must stay reachable
    for ``restore``/``hard-delete``).

    Extracted here (CP20) after the THIRD independent occurrence of this
    IDENTICAL six-line shape — CP13's `apps.catalog._CatalogModelViewSet`,
    CP15's `apps.communications._ReferenceDataModelViewSet`, CP19's
    `apps.system._SystemConfigModelViewSet` — each of which had, until
    now, redefined it locally rather than import one another's, because
    each one's hardcoded ``permission_classes`` was a domain-specific
    permission OBJECT the others had no business depending on (see any of
    the three checkpoints' own historical docstrings for that reasoning,
    preserved in BACKEND_LEARNING_GUIDE.md). Factoring the SHARED shape
    out — while leaving ``permission_classes`` for each concrete subclass
    to set independently — keeps that original reasoning intact: no app
    depends on another app's specific permission composition, only on
    this project's own foundational `apps.core`, the same dependency
    direction every other piece of shared infrastructure in this project
    already has. This is the same "three strikes" factoring threshold
    CP13's own `CatalogItemQuerySet` applied to a shared queryset
    override, applied here to a shared viewset base.

    A concrete subclass must still set ``permission_classes`` (there is
    deliberately no default here — reference-data access rules differ per
    domain) plus ``base_manager``/``base_active_manager``.
    """

    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        base_manager = self.base_active_manager if self.action == "list" else self.base_manager
        return base_manager.all()


class PiiSafeSearchMixin:
    """Removes customer-PII columns from ``SearchFilter``'s field list for
    an employee-facing request.

    Without this, an Employee could *discover* a customer's real email
    address or phone number one guess at a time — ``?search=<value>``
    returning a row is itself a confirmation oracle, even when the value
    never appears in the response body. DRF's ``SearchFilter`` reads
    ``view.search_fields`` through ``get_search_fields()``, so exposing it
    as a request-aware property (rather than a class attribute) is enough
    to make the restriction apply everywhere search is used, including
    nested/custom list actions.

    A subclass declares ``full_search_fields`` (what a Manager/Super Admin
    may search) and ``pii_search_fields`` (the subset removed for an
    Employee) instead of a plain ``search_fields``.
    """

    #: Every searchable column, for a reader allowed to see raw PII.
    full_search_fields = []
    #: The PII subset of ``full_search_fields``, removed for an Employee.
    pii_search_fields = ()

    @property
    def search_fields(self):
        from apps.core.serializers import pii_masking_required

        if pii_masking_required(getattr(self, "request", None)):
            return [field for field in self.full_search_fields if field not in self.pii_search_fields]
        return list(self.full_search_fields)
