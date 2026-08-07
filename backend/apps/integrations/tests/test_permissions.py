"""CP18: tests for apps/integrations/permissions.py. All DB-free."""
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.accounts.permissions import resolve_owner
from apps.integrations import permissions as integrations_permissions
from apps.integrations.models import APIKey, Integration, WebhookDelivery, WebhookEndpoint

User = get_user_model()


class DummyRequest:
    def __init__(self, user):
        self.user = user


class DummyView:
    pass


def _user(role, email):
    return User(email=email, role=role)


def test_reexported_class_is_the_same_object_as_accounts_permissions():
    assert integrations_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin


def test_resolve_owner_finds_integration_owner_field():
    owner = _user(User.Role.EMPLOYEE, "o1@example.com")
    assert resolve_owner(Integration(owner=owner)) is owner


def test_resolve_owner_finds_apikey_owner_property():
    owner = _user(User.Role.EMPLOYEE, "o2@example.com")
    integration = Integration(name="I", owner=owner)
    assert resolve_owner(APIKey(integration=integration)) is owner


def test_resolve_owner_finds_webhookendpoint_owner_property():
    owner = _user(User.Role.EMPLOYEE, "o3@example.com")
    integration = Integration(name="I", owner=owner)
    assert resolve_owner(WebhookEndpoint(integration=integration)) is owner


def test_resolve_owner_finds_webhookdelivery_owner_property_two_levels_deep():
    owner = _user(User.Role.EMPLOYEE, "o4@example.com")
    integration = Integration(name="I", owner=owner)
    endpoint = WebhookEndpoint(integration=integration)
    assert resolve_owner(WebhookDelivery(endpoint=endpoint)) is owner


def test_owner_can_access_own_integration():
    owner = _user(User.Role.EMPLOYEE, "e1@example.com")
    perm = integrations_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(owner), DummyView(), Integration(owner=owner)) is True


def test_non_owner_employee_denied_integration():
    owner = _user(User.Role.EMPLOYEE, "e2@example.com")
    other = _user(User.Role.EMPLOYEE, "e3@example.com")
    perm = integrations_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(other), DummyView(), Integration(owner=owner)) is False


def test_super_admin_can_access_any_integration():
    owner = _user(User.Role.EMPLOYEE, "e4@example.com")
    admin = _user(User.Role.SUPER_ADMIN, "admin@example.com")
    perm = integrations_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(admin), DummyView(), Integration(owner=owner)) is True
