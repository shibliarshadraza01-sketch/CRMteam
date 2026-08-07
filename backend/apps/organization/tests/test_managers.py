"""CP8: tests for Organization.objects / OrganizationQuerySet."""
import pytest

from apps.organization.models import Organization

# --------------------------------------------------------------------------
# No database required — queryset structure
# --------------------------------------------------------------------------


def test_organization_manager_has_active_helper():
    assert hasattr(Organization.objects, "active")


def test_active_queryset_filters_is_active_without_hitting_db():
    queryset = Organization.objects.active()
    assert len(queryset.query.where) > 0


def test_all_queryset_has_no_filter():
    queryset = Organization.objects.all()
    assert len(queryset.query.where) == 0


# --------------------------------------------------------------------------
# Requires database
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_active_excludes_inactive_organizations():
    Organization.objects.create(name="Active Co", slug="active-co", is_active=True)
    Organization.objects.create(name="Inactive Co", slug="inactive-co", is_active=False)

    names = set(Organization.objects.active().values_list("name", flat=True))

    assert names == {"Active Co"}


@pytest.mark.django_db
def test_objects_all_includes_inactive_organizations():
    Organization.objects.create(name="Active Co", slug="active-co", is_active=True)
    Organization.objects.create(name="Inactive Co", slug="inactive-co", is_active=False)

    names = set(Organization.objects.values_list("name", flat=True))

    assert names == {"Active Co", "Inactive Co"}
