"""Final-completion-pass: tests for the admin-facing Users management API
(GET/POST /api/v1/auth/users/, GET/PATCH /<id>/, POST /<id>/activate|
deactivate/). Requires a real database.
"""
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()

USERS_URL = "/api/v1/auth/users/"


def _detail(pk, suffix=""):
    return f"{USERS_URL}{pk}/{suffix}"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def employee():
    return User.objects.create_user(email="mgmt-employee@example.com", password="x", role=User.Role.EMPLOYEE)


@pytest.fixture
def manager():
    return User.objects.create_user(email="mgmt-manager@example.com", password="x", role=User.Role.MANAGER)


@pytest.fixture
def super_admin():
    return User.objects.create_user(email="mgmt-admin@example.com", password="x", role=User.Role.SUPER_ADMIN)


def test_unauthenticated_denied(client):
    response = client.get(USERS_URL)
    assert response.status_code == 401


def test_employee_can_list_users(client, employee, manager):
    client.force_authenticate(employee)
    response = client.get(USERS_URL)
    assert response.status_code == 200
    assert response.data["count"] >= 2


def test_employee_cannot_create_user(client, employee):
    client.force_authenticate(employee)
    response = client.post(USERS_URL, {"email": "new@example.com", "password": "a-strong-password-1"})
    assert response.status_code == 403


def test_manager_cannot_create_user(client, manager):
    client.force_authenticate(manager)
    response = client.post(USERS_URL, {"email": "new@example.com", "password": "a-strong-password-1"})
    assert response.status_code == 403


def test_super_admin_can_create_user(client, super_admin):
    client.force_authenticate(super_admin)
    response = client.post(
        USERS_URL,
        {"email": "new-hire@example.com", "password": "a-strong-password-1", "first_name": "New", "role": "EMPLOYEE"},
    )
    assert response.status_code == 201
    assert response.data["email"] == "new-hire@example.com"
    assert "password" not in response.data
    created = User.objects.get(email="new-hire@example.com")
    assert created.check_password("a-strong-password-1")


def test_created_user_password_is_actually_hashed(client, super_admin):
    client.force_authenticate(super_admin)
    client.post(USERS_URL, {"email": "hash-check@example.com", "password": "a-strong-password-1"})
    created = User.objects.get(email="hash-check@example.com")
    assert created.password != "a-strong-password-1"
    assert created.password.startswith("pbkdf2_sha256$")


def test_super_admin_can_deactivate_and_reactivate_a_user(client, super_admin, employee):
    client.force_authenticate(super_admin)

    response = client.post(_detail(employee.pk, "deactivate/"))
    assert response.status_code == 200
    employee.refresh_from_db()
    assert employee.is_active is False

    response = client.post(_detail(employee.pk, "activate/"))
    assert response.status_code == 200
    employee.refresh_from_db()
    assert employee.is_active is True


def test_manager_cannot_deactivate_a_user(client, manager, employee):
    client.force_authenticate(manager)
    response = client.post(_detail(employee.pk, "deactivate/"))
    assert response.status_code == 403


def test_deactivated_user_cannot_log_in(client, super_admin, employee):
    client.force_authenticate(super_admin)
    client.post(_detail(employee.pk, "deactivate/"))

    fresh_client = APIClient()
    response = fresh_client.post("/api/v1/auth/login/", {"email": employee.email, "password": "x"})
    assert response.status_code == 401


def test_filter_users_by_role(client, employee, manager, super_admin):
    client.force_authenticate(super_admin)
    response = client.get(USERS_URL, {"role": "MANAGER"})
    emails = {row["email"] for row in response.data["results"]}
    assert manager.email in emails
    assert employee.email not in emails


def test_super_admin_can_patch_a_users_role(client, super_admin, employee):
    client.force_authenticate(super_admin)
    response = client.patch(_detail(employee.pk), {"role": "MANAGER"})
    assert response.status_code == 200
    employee.refresh_from_db()
    assert employee.role == User.Role.MANAGER


def test_employee_cannot_patch_another_users_role(client, employee, manager):
    client.force_authenticate(employee)
    response = client.patch(_detail(manager.pk), {"role": "EMPLOYEE"})
    assert response.status_code == 403
