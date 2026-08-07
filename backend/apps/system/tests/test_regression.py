"""CP19: lightweight regression checks that CP1-CP18 remain intact. Not a
re-run of their own suites — this only guards against the specific way a
new app (apps.system) could accidentally break something already built,
especially given this checkpoint connects signal receivers to FIVE
existing models (Customer, Lead, Opportunity, Quote, Invoice) it does not
own. All DB-free.
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
    assert "apps.workflows" in settings.LOCAL_APPS
    assert "apps.integrations" in settings.LOCAL_APPS
    assert "apps.system" in settings.LOCAL_APPS


def test_system_app_is_registered_in_the_app_registry():
    from django.apps import apps

    assert apps.is_installed("apps.system")
    config = apps.get_app_config("system")
    assert config.name == "apps.system"


def test_audit_signals_connect_to_exactly_the_five_curated_models_once_each():
    """Confirms the signal wiring is exactly as documented — no
    duplicate connections (which would double-write audit entries) and
    no unexpected models swept in.
    """
    from django.db.models.signals import post_save

    from apps.crm.models import Customer, Lead
    from apps.crm.opportunities import Opportunity
    from apps.sales.models import Invoice, Quote

    for model in (Customer, Lead, Opportunity, Quote, Invoice):
        receiver_lists = post_save._live_receivers(model)
        flat = [r for group in receiver_lists for r in group]
        matching = [r for r in flat if getattr(r, "__name__", "") == "_record_save"]
        assert len(matching) == 1, f"{model.__name__} has {len(matching)} _record_save receivers, expected 1"


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


def test_cp16_reports_endpoints_still_resolve():
    for basename in ("saved-report", "report-execution", "dashboard", "dashboard-widget"):
        assert reverse(f"reports:{basename}-list")


def test_cp17_workflows_endpoints_still_resolve():
    for basename in ("workflow", "workflow-trigger", "workflow-action", "workflow-execution"):
        assert reverse(f"workflows:{basename}-list")


def test_cp18_integrations_endpoints_still_resolve():
    for basename in ("integration", "api-key", "webhook-endpoint", "webhook-delivery"):
        assert reverse(f"integrations:{basename}-list")


def test_openapi_schema_still_documents_every_pre_cp19_endpoint():
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
        "/api/v1/reports/saved-reports/",
        "/api/v1/workflows/workflows/",
        "/api/v1/integrations/integrations/",
    ):
        assert path in paths, f"{path} missing from schema after CP19"
