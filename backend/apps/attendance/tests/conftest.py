"""Shared fixtures for the attendance app's DB-dependent tests."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="attendance-employee@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def other_employee(db, django_user_model):
    return django_user_model.objects.create_user(
        email="attendance-employee2@example.com", password="x", role=django_user_model.Role.EMPLOYEE
    )


@pytest.fixture
def manager(db, django_user_model):
    return django_user_model.objects.create_user(
        email="attendance-manager@example.com", password="x", role=django_user_model.Role.MANAGER
    )


@pytest.fixture
def super_admin(db, django_user_model):
    return django_user_model.objects.create_user(
        email="attendance-admin@example.com", password="x", role=django_user_model.Role.SUPER_ADMIN
    )


@pytest.fixture
def organization(db):
    from apps.organization.models import Organization

    return Organization.objects.create(name="Attendance Test Org", slug="attendance-test-org")


@pytest.fixture
def department(db, organization):
    from apps.organization.models import Department

    return Department.objects.create(organization=organization, name="Attendance Test Dept")


@pytest.fixture
def team(db, department, manager, employee):
    from apps.organization.models import Membership, Team

    team = Team.objects.create(department=department, name="Attendance Test Team", manager=manager)
    Membership.objects.create(team=team, user=employee)
    return team


@pytest.fixture
def shift_config(db):
    from apps.attendance.models import ShiftConfiguration

    return ShiftConfiguration.objects.create(
        shift_duration_minutes=540,
        idle_timeout_minutes=5,
        allowed_break_minutes=60,
        is_salary_enabled=True,
        hourly_rate=20,
        overtime_multiplier=1.5,
    )
