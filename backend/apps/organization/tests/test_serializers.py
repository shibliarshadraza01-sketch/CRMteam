"""CP8: tests for apps/organization/serializers.py.

Building a serializer and inspecting its ``.fields``/``Meta`` does not
require a database — Django's model introspection (what fields a model
has, their types) is already loaded once ``apps.setup()`` has run, no query
involved. Only tests that construct a serializer *from a real instance and
call `.data`* (which reads relation attributes that may trigger a query)
are marked DB-dependent below.
"""
import pytest
from rest_framework import serializers

from apps.organization.serializers import (
    DepartmentDetailSerializer,
    DepartmentSerializer,
    MembershipDetailSerializer,
    MembershipSerializer,
    OrganizationSerializer,
    TeamDetailSerializer,
    TeamSerializer,
)

# --------------------------------------------------------------------------
# No database required — field declarations
# --------------------------------------------------------------------------


def test_organization_serializer_fields():
    fields = OrganizationSerializer().fields
    assert set(fields.keys()) == {
        "id", "name", "slug", "is_active",
        "created_at", "updated_at", "created_by", "updated_by",
    }


def test_organization_serializer_timestamp_and_audit_fields_are_read_only():
    fields = OrganizationSerializer().fields
    for name in ("created_at", "updated_at", "created_by", "updated_by"):
        assert fields[name].read_only is True


def test_organization_serializer_business_fields_are_writable():
    fields = OrganizationSerializer().fields
    for name in ("name", "slug", "is_active"):
        assert fields[name].read_only is False


def test_department_serializer_fields():
    fields = DepartmentSerializer().fields
    assert {"id", "organization", "name", "description"} <= set(fields.keys())


def test_department_serializer_organization_is_writable_pk_field():
    field = DepartmentSerializer().fields["organization"]
    assert isinstance(field, serializers.PrimaryKeyRelatedField)
    assert field.read_only is False


def test_department_detail_serializer_is_entirely_read_only():
    fields = DepartmentDetailSerializer().fields
    assert "organization_name" in fields
    for name, field in fields.items():
        assert field.read_only is True, f"{name} should be read-only on the detail serializer"


def test_team_serializer_manager_is_writable_pk_field():
    field = TeamSerializer().fields["manager"]
    assert isinstance(field, serializers.PrimaryKeyRelatedField)
    assert field.read_only is False
    assert field.allow_null is True


def test_team_detail_serializer_nests_manager_as_user_serializer():
    fields = TeamDetailSerializer().fields
    manager_field = fields["manager"]
    assert isinstance(manager_field, serializers.Serializer)
    assert manager_field.read_only is True
    assert "department_name" in fields


def test_team_detail_serializer_is_entirely_read_only():
    for name, field in TeamDetailSerializer().fields.items():
        assert field.read_only is True, f"{name} should be read-only on the detail serializer"


def test_membership_serializer_fields():
    fields = MembershipSerializer().fields
    assert {"id", "user", "team", "role", "joined_at"} <= set(fields.keys())


def test_membership_serializer_role_is_writable_choice_field():
    field = MembershipSerializer().fields["role"]
    assert isinstance(field, serializers.ChoiceField)
    assert field.read_only is False


def test_membership_detail_serializer_nests_user_and_team_name():
    fields = MembershipDetailSerializer().fields
    assert isinstance(fields["user"], serializers.Serializer)
    assert fields["user"].read_only is True
    assert "team_name" in fields


def test_membership_detail_serializer_is_entirely_read_only():
    for name, field in MembershipDetailSerializer().fields.items():
        assert field.read_only is True, f"{name} should be read-only on the detail serializer"


# --------------------------------------------------------------------------
# Requires database — serializing a real, persisted instance
#
# (OrganizationSerializer's `name`/`slug` are `unique=True` on the model,
# so DRF's ModelSerializer auto-attaches a UniqueValidator to each — which
# queries the database during is_valid() to check for a clash. That makes
# the "client-supplied read-only fields are silently dropped" check below
# DB-dependent too, unlike CP7's equivalent test, which had no unique
# fields to trigger this.)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_writable_serializers_reject_client_supplied_audit_fields():
    serializer = OrganizationSerializer(
        data={"name": "Acme", "slug": "acme", "created_by": 999, "created_at": "2020-01-01T00:00:00Z"}
    )
    assert serializer.is_valid(), serializer.errors
    assert "created_by" not in serializer.validated_data
    assert "created_at" not in serializer.validated_data


@pytest.mark.django_db
def test_team_detail_serializer_output_includes_nested_manager(django_user_model):
    from apps.organization.models import Department, Organization, Team

    org = Organization.objects.create(name="Acme", slug="acme")
    dept = Department.objects.create(organization=org, name="Sales")
    manager = django_user_model.objects.create_user(
        email="mgr@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    team = Team.objects.create(department=dept, name="Alpha", manager=manager)

    data = TeamDetailSerializer(team).data

    assert data["manager"]["email"] == "mgr@example.com"
    assert data["department_name"] == "Sales"
