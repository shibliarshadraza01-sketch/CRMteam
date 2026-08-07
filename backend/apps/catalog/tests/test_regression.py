"""CP13: lightweight regression checks that CP1-CP12 remain intact. Not a
re-run of their own suites — this only guards against the specific way a
new app (apps.catalog) could accidentally break something already built.
All DB-free.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.accounts.permissions import IsManager, IsSuperAdmin
from apps.core.models import SoftDeleteTimeStampedModel

User = get_user_model()


def test_all_expected_apps_still_installed():
    assert "apps.accounts" in settings.LOCAL_APPS
    assert "apps.core" in settings.LOCAL_APPS
    assert "apps.organization" in settings.LOCAL_APPS
    assert "apps.crm" in settings.LOCAL_APPS
    assert "apps.sales" in settings.LOCAL_APPS
    assert "apps.catalog" in settings.LOCAL_APPS


def test_catalog_app_is_registered_in_the_app_registry():
    from django.apps import apps

    assert apps.is_installed("apps.catalog")
    config = apps.get_app_config("catalog")
    assert config.name == "apps.catalog"


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


def test_cp10_and_cp11_crm_endpoints_still_resolve():
    for basename in ("customer", "lead", "contact", "address", "opportunity"):
        assert reverse(f"crm:{basename}-list")


def test_cp12_sales_endpoints_still_resolve():
    assert reverse("sales:quote-list")
    assert reverse("sales:invoice-list")
    assert reverse("sales:quote-convert", args=[1])


def test_openapi_schema_still_documents_every_pre_cp13_endpoint():
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    for path in (
        "/api/v1/auth/login/",
        "/api/v1/crm/customers/",
        "/api/v1/crm/opportunities/",
        "/api/v1/sales/quotes/",
        "/api/v1/sales/invoices/",
    ):
        assert path in paths, f"{path} missing from schema after CP13"
