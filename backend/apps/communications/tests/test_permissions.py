"""CP15: tests for apps/communications/permissions.py. All DB-free."""
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.accounts.permissions import resolve_owner
from apps.communications import permissions as comms_permissions
from apps.communications.models import CommunicationLog, EmailMessage, Notification
from apps.communications.permissions import EmailTemplateWritePermission

User = get_user_model()


class DummyRequest:
    def __init__(self, user, method="GET"):
        self.user = user
        self.method = method


class DummyView:
    pass


def _user(role, email):
    return User(email=email, role=role)


def test_reexported_owner_permission_is_the_same_object():
    assert comms_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin


def test_resolve_owner_finds_email_message_owner_field():
    owner = _user(User.Role.EMPLOYEE, "o1@example.com")
    assert resolve_owner(EmailMessage(owner=owner)) is owner


def test_resolve_owner_finds_notification_owner_property():
    recipient = _user(User.Role.EMPLOYEE, "r1@example.com")
    assert resolve_owner(Notification(recipient=recipient)) is recipient


def test_resolve_owner_finds_communicationlog_owner_property():
    actor = _user(User.Role.EMPLOYEE, "a1@example.com")
    assert resolve_owner(CommunicationLog(actor=actor)) is actor


def test_email_template_permission_employee_can_read():
    perm = EmailTemplateWritePermission()
    employee = _user(User.Role.EMPLOYEE, "e@example.com")
    assert perm.has_permission(DummyRequest(employee, "GET"), DummyView()) is True


def test_email_template_permission_employee_cannot_write():
    perm = EmailTemplateWritePermission()
    employee = _user(User.Role.EMPLOYEE, "e@example.com")
    assert perm.has_permission(DummyRequest(employee, "POST"), DummyView()) is False


def test_email_template_permission_manager_can_write():
    perm = EmailTemplateWritePermission()
    manager = _user(User.Role.MANAGER, "m@example.com")
    assert perm.has_permission(DummyRequest(manager, "POST"), DummyView()) is True


def test_email_template_permission_anonymous_denied():
    class Anonymous:
        is_authenticated = False

    perm = EmailTemplateWritePermission()
    assert perm.has_permission(DummyRequest(Anonymous(), "GET"), DummyView()) is False


def test_owner_can_access_own_email_message():
    owner = _user(User.Role.EMPLOYEE, "e2@example.com")
    perm = comms_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(owner), DummyView(), EmailMessage(owner=owner)) is True


def test_non_owner_employee_denied_email_message():
    owner = _user(User.Role.EMPLOYEE, "e3@example.com")
    other = _user(User.Role.EMPLOYEE, "e4@example.com")
    perm = comms_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(other), DummyView(), EmailMessage(owner=owner)) is False


def test_super_admin_can_access_any_notification():
    recipient = _user(User.Role.EMPLOYEE, "e5@example.com")
    admin = _user(User.Role.SUPER_ADMIN, "admin@example.com")
    perm = comms_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(admin), DummyView(), Notification(recipient=recipient)) is True
