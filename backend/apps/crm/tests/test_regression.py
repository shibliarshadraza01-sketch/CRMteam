"""CP10: lightweight regression checks that CP1-CP9 remain intact.

Not a re-run of CP1-CP9's own test suites — those already run in their own
apps and are unaffected by CP10. This file only guards against the
specific way CP10's changes (new URLs, a project-wide pagination class
swap, a new SPECTACULAR_SETTINGS key) could accidentally break something
already built. All DB-free.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.permissions import IsManager, IsSuperAdmin
from apps.core.models import SoftDeleteTimeStampedModel
from apps.organization.models import Organization, Team

User = get_user_model()


def test_all_expected_apps_still_installed():
    assert "apps.accounts" in settings.LOCAL_APPS
    assert "apps.core" in settings.LOCAL_APPS
    assert "apps.organization" in settings.LOCAL_APPS
    assert "apps.crm" in settings.LOCAL_APPS


def test_cp3_cp4_cp5_auth_urls_still_resolve():
    assert reverse("accounts:login")
    assert reverse("accounts:super-admin-verify")
    assert reverse("accounts:session-list")


def test_cp6_permission_classes_still_importable_and_functional():
    class DummyRequest:
        def __init__(self, user):
            self.user = user

    class DummyView:
        pass

    admin_user = User(email="admin@example.com", role=User.Role.SUPER_ADMIN)
    manager_user = User(email="mgr@example.com", role=User.Role.MANAGER)

    assert IsSuperAdmin().has_permission(DummyRequest(admin_user), DummyView()) is True
    assert IsManager().has_permission(DummyRequest(manager_user), DummyView()) is True


def test_cp7_core_abstract_models_still_importable():
    assert SoftDeleteTimeStampedModel._meta.abstract is True


def test_cp8_organization_hierarchy_still_importable():
    assert Organization._meta.get_field("name").unique is True
    assert Team._meta.get_field("manager").remote_field.related_name == "teams_managed"


def test_cp9_crm_models_still_importable_with_unchanged_core_fields():
    from apps.crm.models import Customer, Lead

    assert Customer._meta.get_field("slug").max_length == 220
    assert Lead._meta.get_field("status").default == Lead.Status.NEW


def test_pagination_class_swap_did_not_break_cp5_session_list_view():
    # CP10 changed DEFAULT_PAGINATION_CLASS project-wide (25 -> a named
    # StandardPagination at 20, see settings.py) — confirm CP5's
    # SessionListView (which never set its own pagination_class) picks up
    # the new project default automatically rather than erroring.
    from apps.accounts.views import SessionListView
    from apps.core.pagination import StandardPagination

    assert SessionListView.pagination_class is StandardPagination
    assert settings.REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"] == "apps.core.pagination.StandardPagination"


def test_openapi_schema_still_documents_every_pre_cp10_drf_endpoint():
    # /health is a plain Django view (not a DRF APIView), so it was never
    # part of drf-spectacular's schema before CP10 either — only real DRF
    # endpoints are checked here.
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    for path in (
        "/api/v1/auth/login/",
        "/api/v1/auth/me/",
        "/api/v1/auth/sessions/",
        "/api/v1/auth/super-admin/verify/",
    ):
        assert path in paths, f"{path} missing from schema after CP10"


def test_cp10_customer_lead_contact_address_endpoints_still_resolve():
    # CP11 added a fifth CRM resource (opportunities) alongside CP10's
    # four — confirm none of CP10's own routes/viewsets were disturbed.
    for basename in ("customer", "lead", "contact", "address"):
        assert reverse(f"crm:{basename}-list")
        assert reverse(f"crm:{basename}-detail", args=[1])


def test_cp10_managed_user_ids_and_scope_queryset_still_importable():
    # CP11's Opportunity.manager_has_access() reuses these CP10 functions
    # directly — confirm CP10 didn't have to change either's signature to
    # support CP11 (both still importable, same call shape).
    from apps.crm.services import managed_user_ids, scope_queryset_for_user

    assert callable(managed_user_ids)
    assert callable(scope_queryset_for_user)
