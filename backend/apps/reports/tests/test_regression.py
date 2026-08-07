"""CP16: lightweight regression checks that CP1-CP15 remain intact. Not a
re-run of their own suites — this only guards against the specific way a
new app (apps.reports) could accidentally break something already built,
especially given this checkpoint's report computations query directly
into apps.crm/apps.crm.opportunities/apps.activities models. All DB-free.
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
    assert "apps.activities" in settings.LOCAL_APPS
    assert "apps.communications" in settings.LOCAL_APPS
    assert "apps.reports" in settings.LOCAL_APPS


def test_reports_app_is_registered_in_the_app_registry():
    from django.apps import apps

    assert apps.is_installed("apps.reports")
    config = apps.get_app_config("reports")
    assert config.name == "apps.reports"


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


def test_cp13_catalog_endpoints_still_resolve():
    for basename in ("product", "service", "pricebook", "pricebook-entry"):
        assert reverse(f"catalog:{basename}-list")


def test_cp14_activities_endpoints_still_resolve():
    for basename in ("task", "event", "activity-log", "reminder"):
        assert reverse(f"activities:{basename}-list")


def test_cp15_communications_endpoints_still_resolve():
    for basename in ("email-template", "email-message", "notification", "communication-log"):
        assert reverse(f"communications:{basename}-list")


def test_cp9_cp11_cp14_models_this_checkpoint_computes_from_are_unchanged():
    """This checkpoint's report computations import Lead (CP9),
    Opportunity (CP11), Task/ActivityLog (CP14) directly — confirms those
    imports still resolve and expose the fields ``services.py`` relies on.
    """
    from apps.activities.models import ActivityLog, Task
    from apps.crm.models import Lead
    from apps.crm.opportunities import Opportunity

    assert {"owner", "converted_customer", "created_at"} <= {f.name for f in Lead._meta.get_fields()}
    assert {"owner", "stage", "is_closed", "value"} <= {f.name for f in Opportunity._meta.get_fields()}
    assert {"assigned_to", "status", "completed_at"} <= {f.name for f in Task._meta.get_fields()}
    assert {"actor", "occurred_at", "content_type", "object_id"} <= {f.name for f in ActivityLog._meta.get_fields()}


def test_openapi_schema_still_documents_every_pre_cp16_endpoint():
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]
    for path in (
        "/api/v1/auth/login/",
        "/api/v1/crm/customers/",
        "/api/v1/crm/opportunities/",
        "/api/v1/sales/quotes/",
        "/api/v1/sales/invoices/",
        "/api/v1/catalog/products/",
        "/api/v1/activities/tasks/",
        "/api/v1/communications/email-templates/",
    ):
        assert path in paths, f"{path} missing from schema after CP16"
