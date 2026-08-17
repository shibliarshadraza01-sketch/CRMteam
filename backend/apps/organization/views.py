"""Final-completion-pass: the organization hierarchy's REST API.

CP8 built the models/serializers/permissions/services but deliberately no
HTTP surface ("that is a deliberately separate, larger concern" — see
models.py). That surface is now required: the frontend's Customer-create
flow needs a real way to list/select an ``Organization``, and Users/Team
needs a real way to browse the org chart and team memberships.

None of these models mix in CP7's soft-delete (see models.py's own
docstring for why) — so this app uses CP7's ``AuditStampedModelMixin``
alone (stamps created_by/updated_by), not the full
``SoftDeleteAuditModelViewSetMixin`` combination every other CP9+ app
uses. DELETE is a real, permanent delete here, exactly matching the
CASCADE relationships already defined in models.py — deleting an
Organization was always going to cascade-delete its Departments/Teams/
Memberships; there is no "undo" concept to preserve.
"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.views import AuditStampedModelMixin
from apps.crm.services import scope_queryset_for_user

from .filters import DepartmentFilterSet, MembershipFilterSet, OrganizationFilterSet, TeamFilterSet
from .models import Department, Membership, Organization, Team
from .permissions import DepartmentTeamWritePermission, IsOwnerOrSuperAdmin, OrganizationWritePermission
from .serializers import (
    DepartmentDetailSerializer,
    DepartmentSerializer,
    MembershipDetailSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    TeamDetailSerializer,
    TeamSerializer,
)


class OrganizationViewSet(AuditStampedModelMixin, viewsets.ModelViewSet):
    """Read: any authenticated user. Write: Super Admin only — creating or
    renaming a tenant-level organization is not a Manager-level decision.
    """

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    filterset_class = OrganizationFilterSet
    permission_classes = [IsAuthenticated, OrganizationWritePermission]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["name"]


class DepartmentViewSet(AuditStampedModelMixin, viewsets.ModelViewSet):
    """Read: any authenticated user. Write: Manager or above."""

    queryset = Department.objects.select_related("organization")
    serializer_class = DepartmentSerializer
    filterset_class = DepartmentFilterSet
    permission_classes = [IsAuthenticated, DepartmentTeamWritePermission]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["organization", "name"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DepartmentDetailSerializer
        return DepartmentSerializer


class TeamViewSet(AuditStampedModelMixin, viewsets.ModelViewSet):
    """Read: any authenticated user. Write: Manager or above."""

    queryset = Team.objects.select_related("department", "manager")
    serializer_class = TeamSerializer
    filterset_class = TeamFilterSet
    permission_classes = [IsAuthenticated, DepartmentTeamWritePermission]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at", "updated_at"]
    ordering = ["department", "name"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TeamDetailSerializer
        return TeamSerializer


class MembershipViewSet(AuditStampedModelMixin, viewsets.ModelViewSet):
    """List/retrieve scoped like every CP10 owner-based resource (CP6's
    ``IsOwnerOrSuperAdmin`` + CP10's ``scope_queryset_for_user()``): a
    plain Employee sees only their own memberships, a Manager sees their
    own plus every member of every team they manage, a Super Admin sees
    everything. Create/update/delete are gated the same way at the object
    level.
    """

    queryset = Membership.objects.select_related("user", "team")
    serializer_class = MembershipSerializer
    filterset_class = MembershipFilterSet
    permission_classes = [IsAuthenticated, IsOwnerOrSuperAdmin]
    ordering_fields = ["joined_at", "created_at", "updated_at"]
    ordering = ["team", "user"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MembershipDetailSerializer
        return MembershipSerializer

    def get_queryset(self):
        return scope_queryset_for_user(super().get_queryset(), self.request.user, owner_field="user")
