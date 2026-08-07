"""CP16: tests for apps/reports/permissions.py. All DB-free."""
from django.contrib.auth import get_user_model

from apps.accounts import permissions as accounts_permissions
from apps.accounts.permissions import resolve_owner
from apps.reports import permissions as reports_permissions
from apps.reports.models import Dashboard, DashboardWidget, ReportExecution, SavedReport

User = get_user_model()


class DummyRequest:
    def __init__(self, user):
        self.user = user


class DummyView:
    pass


def _user(role, email):
    return User(email=email, role=role)


def test_reexported_class_is_the_same_object_as_accounts_permissions():
    assert reports_permissions.IsOwnerOrSuperAdmin is accounts_permissions.IsOwnerOrSuperAdmin


def test_resolve_owner_finds_saved_report_owner_field():
    owner = _user(User.Role.EMPLOYEE, "o1@example.com")
    assert resolve_owner(SavedReport(owner=owner)) is owner


def test_resolve_owner_finds_dashboard_owner_field():
    owner = _user(User.Role.EMPLOYEE, "o2@example.com")
    assert resolve_owner(Dashboard(owner=owner)) is owner


def test_resolve_owner_finds_report_execution_owner_property():
    owner = _user(User.Role.EMPLOYEE, "o3@example.com")
    report = SavedReport(name="R", owner=owner)
    assert resolve_owner(ReportExecution(report=report)) is owner


def test_resolve_owner_finds_dashboard_widget_owner_property():
    owner = _user(User.Role.EMPLOYEE, "o4@example.com")
    dashboard = Dashboard(name="D", owner=owner)
    assert resolve_owner(DashboardWidget(dashboard=dashboard)) is owner


def test_owner_can_access_own_saved_report():
    owner = _user(User.Role.EMPLOYEE, "e1@example.com")
    perm = reports_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(owner), DummyView(), SavedReport(owner=owner)) is True


def test_non_owner_employee_denied_saved_report():
    owner = _user(User.Role.EMPLOYEE, "e2@example.com")
    other = _user(User.Role.EMPLOYEE, "e3@example.com")
    perm = reports_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(other), DummyView(), SavedReport(owner=owner)) is False


def test_super_admin_can_access_any_dashboard():
    owner = _user(User.Role.EMPLOYEE, "e4@example.com")
    admin = _user(User.Role.SUPER_ADMIN, "admin@example.com")
    perm = reports_permissions.IsOwnerOrSuperAdmin()
    assert perm.has_object_permission(DummyRequest(admin), DummyView(), Dashboard(owner=owner)) is True
