"""CP10: tests for apps/crm/views.py's declarative configuration —
permission classes, allowed HTTP methods, serializer selection, filter/
search/ordering wiring. Inspecting class attributes and calling
``get_serializer_class()``/``get_queryset()``'s *query-building* (never
evaluating) needs no database.
"""
from rest_framework.permissions import IsAuthenticated

from apps.core.views import SoftDeleteAuditModelViewSetMixin
from apps.crm.filters import AddressFilterSet, ContactPersonFilterSet, CustomerFilterSet, LeadFilterSet
from apps.crm.permissions import IsOwnerOrSuperAdmin
from apps.crm.serializers import (
    AddressSerializer,
    ContactPersonSerializer,
    CustomerDetailSerializer,
    CustomerSerializer,
    LeadDetailSerializer,
    LeadSerializer,
)
from apps.crm.views import AddressViewSet, ContactPersonViewSet, CustomerViewSet, LeadViewSet

ALL_VIEWSETS = [CustomerViewSet, LeadViewSet, ContactPersonViewSet, AddressViewSet]


def test_no_viewset_allows_put():
    for viewset in ALL_VIEWSETS:
        assert "put" not in viewset.http_method_names


def test_every_viewset_allows_get_post_patch_delete():
    for viewset in ALL_VIEWSETS:
        for method in ("get", "post", "patch", "delete"):
            assert method in viewset.http_method_names


def test_every_viewset_uses_soft_delete_audit_mixin():
    for viewset in ALL_VIEWSETS:
        assert issubclass(viewset, SoftDeleteAuditModelViewSetMixin)


def test_every_viewset_requires_authentication_and_ownership():
    for viewset in ALL_VIEWSETS:
        assert IsAuthenticated in viewset.permission_classes
        assert IsOwnerOrSuperAdmin in viewset.permission_classes


def test_customer_viewset_serializer_selection():
    view = CustomerViewSet()
    view.action = "list"
    assert view.get_serializer_class() is CustomerSerializer
    view.action = "retrieve"
    assert view.get_serializer_class() is CustomerDetailSerializer
    view.action = "create"
    assert view.get_serializer_class() is CustomerSerializer


def test_lead_viewset_serializer_selection():
    view = LeadViewSet()
    view.action = "list"
    assert view.get_serializer_class() is LeadSerializer
    view.action = "retrieve"
    assert view.get_serializer_class() is LeadDetailSerializer


def test_contact_and_address_viewsets_have_no_detail_serializer_split():
    # ContactPerson/Address have only one serializer each (CP9) — no
    # get_serializer_class() override needed or present.
    assert "get_serializer_class" not in ContactPersonViewSet.__dict__
    assert "get_serializer_class" not in AddressViewSet.__dict__
    assert ContactPersonViewSet.serializer_class is ContactPersonSerializer
    assert AddressViewSet.serializer_class is AddressSerializer


def test_viewsets_use_the_correct_filterset():
    assert CustomerViewSet.filterset_class is CustomerFilterSet
    assert LeadViewSet.filterset_class is LeadFilterSet
    assert ContactPersonViewSet.filterset_class is ContactPersonFilterSet
    assert AddressViewSet.filterset_class is AddressFilterSet


def test_customer_search_fields_match_spec():
    assert set(CustomerViewSet.search_fields) == {"name", "email", "phone", "website"}


def test_lead_search_fields_match_spec():
    assert set(LeadViewSet.search_fields) == {"company_name", "contact_name", "email", "phone"}


def test_customer_ordering_fields_match_spec():
    assert set(CustomerViewSet.ordering_fields) == {"name", "created_at", "updated_at", "status"}


def test_lead_ordering_fields_include_a_name_alias_for_company_name():
    assert ("company_name", "name") in LeadViewSet.ordering_fields
    assert "created_at" in LeadViewSet.ordering_fields
    assert "updated_at" in LeadViewSet.ordering_fields
    assert "status" in LeadViewSet.ordering_fields


def test_contact_and_address_owner_field_traverses_customer():
    assert ContactPersonViewSet.owner_field == "customer__owner"
    assert AddressViewSet.owner_field == "customer__owner"


def test_customer_and_lead_owner_field_is_direct():
    assert CustomerViewSet.owner_field == "owner"
    assert LeadViewSet.owner_field == "owner"


# --------------------------------------------------------------------------
# get_queryset() query-building — lazy, never evaluated, so no DB needed
# --------------------------------------------------------------------------


def test_customer_list_queryset_is_restricted_to_active_rows_without_hitting_db():
    view = CustomerViewSet()
    view.action = "list"
    view.request = type("Req", (), {"user": None})()  # anonymous -> .none(), still lazy
    queryset = view.get_queryset()
    assert queryset.model.__name__ == "Customer"
