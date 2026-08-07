"""CP8: lightweight regression checks that CP1-CP7 remain intact.

Not a re-run of CP1-CP7's own test suites (those already run in their own
apps and are unaffected by CP8 — see BACKEND_PROGRESS.md's regression
sections for their own pass/blocked counts). This file only guards against
the specific way a *new* app could accidentally break something already
built: an app-registry/settings mistake, an accidental import-time side
effect, or a related_name collision with an existing model. All DB-free —
these are exactly the kind of mistakes that show up without ever touching
the database.
"""
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.accounts.permissions import IsManager, IsSuperAdmin
from apps.core.models import TimeStampedModel

User = get_user_model()


def test_all_expected_apps_still_installed():
    assert "apps.accounts" in settings.LOCAL_APPS
    assert "apps.core" in settings.LOCAL_APPS
    assert "apps.organization" in settings.LOCAL_APPS


def test_organization_app_is_registered_in_the_app_registry():
    assert apps.is_installed("apps.organization")
    config = apps.get_app_config("organization")
    assert config.name == "apps.organization"


def test_auth_user_model_unchanged():
    assert settings.AUTH_USER_MODEL == "accounts.User"
    assert User.USERNAME_FIELD == "email"


def test_cp3_cp4_cp5_auth_urls_still_resolve():
    # Spot-check a representative endpoint from each of CP3/CP4/CP5 rather
    # than re-enumerating the full list (already covered by CP3/CP4/CP5's
    # own tests) — this only guards against CP8 having broken URL inclusion.
    from django.urls import reverse

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
    assert TimeStampedModel._meta.abstract is True
    assert {"created_at", "updated_at"} <= {f.name for f in TimeStampedModel._meta.get_fields()}


def test_organization_related_names_do_not_collide_with_existing_user_relations():
    # User already has `sessions` (CP5) and `teams_managed`/`team_memberships`
    # (CP8) — confirm both sets of reverse accessors coexist without
    # shadowing one another.
    assert hasattr(User, "sessions")
    assert hasattr(User, "teams_managed")
    assert hasattr(User, "team_memberships")
