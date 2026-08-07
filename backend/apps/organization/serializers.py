"""CP8: serializers for the organization hierarchy.

Every serializer mixes in CP7's ``TimeStampedSerializerMixin``/
``AuditSerializerMixin`` (``apps.core.serializers``) so ``created_at``/
``updated_at``/``created_by``/``updated_by`` are exposed read-only in
exactly the same shape CP7 already established, rather than being
redeclared here.

Two kinds of serializer are provided per model, per CP8's "read-only
serializers where applicable" requirement:

- A **writable** serializer (``TeamSerializer``, ``MembershipSerializer``,
  ...) — foreign keys accepted as plain primary keys, used for
  create/update.
- A **read-only detail** serializer (``TeamDetailSerializer``,
  ``MembershipDetailSerializer``) — the same data plus nested
  representations (e.g. the manager's safe user info, not just their ID),
  used for list/detail *output* where a richer, but never writable, shape
  is more useful. These reuse ``apps.accounts.serializers.UserSerializer``
  directly rather than re-declaring a second "safe user" shape.
"""
from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.core.serializers import AuditSerializerMixin, TimeStampedSerializerMixin

from .models import Department, Membership, Organization, Team


class _OrgAuditedSerializer(TimeStampedSerializerMixin, AuditSerializerMixin, serializers.ModelSerializer):
    """Shared base: every organization-app serializer gets the CP7
    timestamp/audit field shape without repeating it per class.
    """


class OrganizationSerializer(_OrgAuditedSerializer):
    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "is_active",
            "created_at", "updated_at", "created_by", "updated_by",
        ]


class DepartmentSerializer(_OrgAuditedSerializer):
    class Meta:
        model = Department
        fields = [
            "id", "organization", "name", "description",
            "created_at", "updated_at", "created_by", "updated_by",
        ]


class DepartmentDetailSerializer(DepartmentSerializer):
    """Read-only: adds the organization's name so a client doesn't have to
    make a second request just to display it alongside a department.
    """

    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta(DepartmentSerializer.Meta):
        fields = DepartmentSerializer.Meta.fields + ["organization_name"]
        read_only_fields = fields


class TeamSerializer(_OrgAuditedSerializer):
    class Meta:
        model = Team
        fields = [
            "id", "department", "name", "manager",
            "created_at", "updated_at", "created_by", "updated_by",
        ]


class TeamDetailSerializer(TeamSerializer):
    """Read-only: nests the manager's safe user info (reusing CP3's
    ``UserSerializer``) instead of exposing only their ID.
    """

    manager = UserSerializer(read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta(TeamSerializer.Meta):
        fields = TeamSerializer.Meta.fields + ["department_name"]
        read_only_fields = fields


class MembershipSerializer(_OrgAuditedSerializer):
    class Meta:
        model = Membership
        fields = [
            "id", "user", "team", "role", "joined_at",
            "created_at", "updated_at", "created_by", "updated_by",
        ]


class MembershipDetailSerializer(MembershipSerializer):
    """Read-only: nests the member's safe user info and the team's name."""

    user = UserSerializer(read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta(MembershipSerializer.Meta):
        fields = MembershipSerializer.Meta.fields + ["team_name"]
        read_only_fields = fields
