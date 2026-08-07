"""CP11: tests confirming CP6's ``IsOwnerOrSuperAdmin`` (unchanged) works
correctly against ``Opportunity``/``OpportunityActivity``/``OpportunityNote``
with zero new permission logic — only the ``manager_has_access()`` hooks
added to ``opportunities.py`` (reusing CP10's ``managed_user_ids()``).

Owner-direct and Super-Admin-override checks never reach
``managed_user_ids()`` and stay genuinely DB-free (same reasoning as CP9's
``test_permissions.py``); the Manager-not-owner path does need a database,
since it queries CP8's ``Team``/``Membership`` models.
"""
import pytest
from django.contrib.auth import get_user_model

from apps.crm.opportunities import Opportunity, OpportunityActivity, OpportunityNote
from apps.crm.permissions import IsOwnerOrSuperAdmin

User = get_user_model()


class DummyRequest:
    def __init__(self, user):
        self.user = user


class DummyView:
    pass


def _user(role, email, pk):
    user = User(email=email, role=role)
    user.pk = pk
    return user


# --------------------------------------------------------------------------
# No database required
# --------------------------------------------------------------------------


def test_opportunity_owner_passes():
    owner = _user(User.Role.EMPLOYEE, "owner@example.com", 1)
    from apps.crm.models import Customer

    opp = Opportunity(title="Deal", customer=Customer(name="Globex"), owner=owner)
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(owner), DummyView(), opp) is True


def test_different_employee_denied_on_someone_elses_opportunity():
    owner = _user(User.Role.EMPLOYEE, "owner@example.com", 1)
    other = _user(User.Role.EMPLOYEE, "other@example.com", 2)
    from apps.crm.models import Customer

    opp = Opportunity(title="Deal", customer=Customer(name="Globex"), owner=owner)
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(other), DummyView(), opp) is False


def test_super_admin_always_passes_regardless_of_ownership():
    admin = _user(User.Role.SUPER_ADMIN, "admin@example.com", 9)
    from apps.crm.models import Customer

    opp = Opportunity(title="Deal", customer=Customer(name="Globex"))  # no owner
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(admin), DummyView(), opp) is True


def test_activity_and_note_owner_resolved_through_opportunity():
    owner = _user(User.Role.EMPLOYEE, "owner@example.com", 1)
    from apps.crm.models import Customer

    opp = Opportunity(title="Deal", customer=Customer(name="Globex"), owner=owner)
    activity = OpportunityActivity(opportunity=opp, subject="Call")
    note = OpportunityNote(opportunity=opp, content="hi")
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(owner), DummyView(), activity) is True
    assert perm.has_object_permission(DummyRequest(owner), DummyView(), note) is True


# --------------------------------------------------------------------------
# Requires database — the Manager-not-owner path (queries Team/Membership)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_team_manager_passes_via_manager_has_access(organization, manager, employee, managed_team):
    from apps.crm.models import Customer

    customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs-perm", owner=employee)
    opp = Opportunity.objects.create(customer=customer, title="Deal", owner=employee)
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(manager), DummyView(), opp) is True


@pytest.mark.django_db
def test_unrelated_manager_denied(organization, employee, django_user_model):
    from apps.crm.models import Customer

    unrelated = django_user_model.objects.create_user(
        email="unrelated-perm@example.com", password="x", role=django_user_model.Role.MANAGER
    )
    customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs-perm2", owner=employee)
    opp = Opportunity.objects.create(customer=customer, title="Deal", owner=employee)
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(unrelated), DummyView(), opp) is False


@pytest.mark.django_db
def test_note_manager_access_delegates_through_opportunity(organization, manager, employee, managed_team):
    from apps.crm.models import Customer

    customer = Customer.objects.create(organization=organization, name="Theirs", slug="theirs-perm3", owner=employee)
    opp = Opportunity.objects.create(customer=customer, title="Deal", owner=employee)
    note = OpportunityNote.objects.create(opportunity=opp, content="hi")
    perm = IsOwnerOrSuperAdmin()

    assert perm.has_object_permission(DummyRequest(manager), DummyView(), note) is True
