"""CP19: the system/platform domain's REST API.

Three different viewset bases, matching `permissions.py`'s three access
shapes:

- `AuditLogViewSet` — a plain DRF `ReadOnlyModelViewSet`, no CP7 mixin at
  all: `AuditLog` has no soft-delete support to mix in
  (`SoftDeleteAuditModelViewSetMixin` assumes `soft_delete()`/`restore()`
  exist, which it deliberately doesn't have) and no `owner` to scope by
  (`_CrmModelViewSet` doesn't apply either) — role-gated only
  (`IsManagerOrSuperAdmin`), every Manager/Super Admin sees the FULL
  audit trail, not a team-scoped slice of it.
- `_SystemConfigModelViewSet` — a small local base for
  `SystemSetting`/`FeatureFlag` (no owner). Its shared no-PUT/active-vs-
  unfiltered shape lives in `apps.core.views.ReferenceDataModelViewSetMixin`
  — factored out at CP20 as the THIRD independent occurrence of it,
  after CP13's `_CatalogModelViewSet`/CP15's `_ReferenceDataModelViewSet`
  (see that mixin's own docstring); only `permission_classes` is set
  here, `SystemConfigWritePermission` being this app's own composition.
- `BackgroundJobViewSet` reuses CP10's `_CrmModelViewSet` directly (a
  real `owner` FK) — the same cross-app reuse CP12/CP14/CP15/CP16/CP17/
  CP18 already established.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.views import ReferenceDataModelViewSetMixin
from apps.crm.services import resolve_owner_for_create
from apps.crm.views import _CrmModelViewSet

from .filters import (
    AuditLogFilterSet,
    BackgroundJobFilterSet,
    FeatureFlagFilterSet,
    SystemSettingFilterSet,
)
from .models import AuditLog, BackgroundJob, FeatureFlag, SystemSetting
from .permissions import IsManagerOrSuperAdmin, SystemConfigWritePermission
from .serializers import (
    AuditLogSerializer,
    BackgroundJobSerializer,
    FeatureFlagSerializer,
    SystemSettingSerializer,
)
from .services import complete_background_job, fail_background_job, start_background_job


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only, Manager-or-above only. No `restore`/`hard-delete` (no
    CP7 mixin at all — see this module's own docstring for why).
    """

    queryset = AuditLog.objects.select_related("actor", "content_type").all()
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilterSet
    permission_classes = [IsAuthenticated, IsManagerOrSuperAdmin]
    search_fields = ["description"]
    ordering_fields = ["created_at", "action"]
    ordering = ["-created_at"]


class _SystemConfigModelViewSet(ReferenceDataModelViewSetMixin, viewsets.ModelViewSet):
    """Shared reference-data base for `SystemSetting`/`FeatureFlag` — see
    this module's own docstring.
    """

    permission_classes = [IsAuthenticated, SystemConfigWritePermission]

    def get_queryset(self):
        """``SystemSetting.active_objects``/``FeatureFlag.active_objects``
        mean "not deleted AND is_active/is_enabled=True" (see models.py) —
        used unmodified via ``base_active_manager``, that would make
        ``is_active``/``is_enabled`` an unfilterable dead field on the list
        endpoint. Re-widen list back to "not deleted" so those stay genuine,
        working filters (matching every other app's list default).
        """
        queryset = super().get_queryset()
        if self.action == "list":
            queryset = self.base_manager.filter(is_deleted=False)
        return queryset


class SystemSettingViewSet(_SystemConfigModelViewSet):
    base_manager = SystemSetting.objects
    base_active_manager = SystemSetting.active_objects
    serializer_class = SystemSettingSerializer
    filterset_class = SystemSettingFilterSet
    search_fields = ["key", "description"]
    ordering_fields = ["key", "created_at", "updated_at"]
    ordering = ["key"]


class FeatureFlagViewSet(_SystemConfigModelViewSet):
    base_manager = FeatureFlag.objects
    base_active_manager = FeatureFlag.active_objects
    serializer_class = FeatureFlagSerializer
    filterset_class = FeatureFlagFilterSet
    search_fields = ["key", "name", "description"]
    ordering_fields = ["key", "created_at", "updated_at"]
    ordering = ["key"]


class BackgroundJobViewSet(_CrmModelViewSet):
    """CRUD (via `_CrmModelViewSet`) plus three lifecycle actions — thin
    wrappers around `services.py`'s state-transition functions, the same
    "custom actions are thin wrappers around services" shape CP11's
    `OpportunityViewSet` established.
    """

    base_manager = BackgroundJob.objects
    base_active_manager = BackgroundJob.active_objects
    serializer_class = BackgroundJobSerializer
    filterset_class = BackgroundJobFilterSet
    search_fields = ["name", "job_type"]
    ordering_fields = ["created_at", "started_at", "completed_at", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return super().get_queryset().select_related("owner")

    def perform_create(self, serializer):
        """Defaults ``owner`` to the requesting user when not explicitly
        supplied — the same rule ``SavedReportViewSet``/``WorkflowViewSet``
        already apply.
        """
        super().perform_create(serializer)
        job = serializer.instance
        resolved_owner = resolve_owner_for_create(self.request.user, job.owner)
        if resolved_owner.pk != job.owner_id:
            job.owner = resolved_owner
            job.save(update_fields=["owner", "updated_at"])

    def _job_response(self, job):
        serializer = self.get_serializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: BackgroundJobSerializer})
    @action(detail=True, methods=["post"])
    def start(self, request, *args, **kwargs):
        """``POST /background-jobs/<id>/start/`` — PENDING -> RUNNING
        (``services.start_background_job()``).
        """
        job = self.get_object()
        try:
            start_background_job(job)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._job_response(job)

    @extend_schema(request=None, responses={200: BackgroundJobSerializer})
    @action(detail=True, methods=["post"])
    def complete(self, request, *args, **kwargs):
        """``POST /background-jobs/<id>/complete/`` — RUNNING -> COMPLETED
        (``services.complete_background_job()``).
        """
        job = self.get_object()
        try:
            complete_background_job(job, result_data=request.data.get("result_data"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._job_response(job)

    @extend_schema(request=None, responses={200: BackgroundJobSerializer})
    @action(detail=True, methods=["post"])
    def fail(self, request, *args, **kwargs):
        """``POST /background-jobs/<id>/fail/`` — RUNNING -> FAILED
        (``services.fail_background_job()``).
        """
        job = self.get_object()
        error_message = request.data.get("error_message", "")
        try:
            fail_background_job(job, error_message)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return self._job_response(job)
