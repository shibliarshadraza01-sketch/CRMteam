"""CP12: lightweight regression checks that CP1-CP11 remain intact. Not a
re-run of their own suites — this only guards against the specific way a
new app (apps.sales) and a new ENUM_NAME_OVERRIDES entry could
accidentally break something already built. All DB-free.
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
    assert "apps.sales" in settings.LOCAL_APPS


def test_sales_app_is_registered_in_the_app_registry():
    from django.apps import apps

    assert apps.is_installed("apps.sales")
    config = apps.get_app_config("sales")
    assert config.name == "apps.sales"


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


def test_cp10_crm_endpoints_still_resolve():
    for basename in ("customer", "lead", "contact", "address"):
        assert reverse(f"crm:{basename}-list")


def test_cp11_opportunity_endpoints_still_resolve():
    assert reverse("crm:opportunity-list")
    assert reverse("crm:opportunity-mark-won", args=[1])


def test_cp10_managed_user_ids_and_scope_queryset_reused_by_sales():
    # apps.sales.models.Quote/Invoice.manager_has_access() calls this
    # exact CP10 function — confirm it's still importable with the same
    # call shape sales depends on.
    from apps.crm.services import managed_user_ids, scope_queryset_for_user

    assert callable(managed_user_ids)
    assert callable(scope_queryset_for_user)


def test_openapi_schema_still_documents_every_pre_cp12_endpoint():
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    for path in (
        "/api/v1/auth/login/",
        "/api/v1/crm/customers/",
        "/api/v1/crm/opportunities/",
    ):
        assert path in paths, f"{path} missing from schema after CP12"
