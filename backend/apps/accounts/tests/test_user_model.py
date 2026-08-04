"""CP2 tests: the custom User model, its manager, and its invariants.

These require a real database connection (pytest-django creates a throwaway
PostgreSQL test database via `migrate`). They cannot run until PostgreSQL is
available — see BACKEND_PROGRESS.md CP2 for the current blocker/status.
"""
import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_create_user_with_valid_email():
    user = User.objects.create_user(email="alice@example.com", password="a-strong-password-1")

    assert user.pk is not None
    assert user.email == "alice@example.com"
    assert user.is_active is True
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.role == User.Role.EMPLOYEE  # default role for normal CRM users


def test_email_is_normalized_to_lowercase():
    user = User.objects.create_user(email="Alice.Manager@Example.COM", password="a-strong-password-1")

    assert user.email == "alice.manager@example.com"


def test_password_is_hashed_not_stored_raw():
    raw_password = "a-strong-password-1"
    user = User.objects.create_user(email="bob@example.com", password=raw_password)

    assert user.password != raw_password
    # Django's default hasher output is self-describing, e.g.
    # "pbkdf2_sha256$<iterations>$<salt>$<hash>".
    assert user.password.startswith("pbkdf2_sha256$")
    assert user.check_password(raw_password) is True
    assert user.check_password("wrong-password") is False


def test_duplicate_email_rejected():
    User.objects.create_user(email="dup@example.com", password="a-strong-password-1")

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@example.com", password="another-password-2")


def test_duplicate_email_rejected_case_insensitively():
    User.objects.create_user(email="dup2@example.com", password="a-strong-password-1")

    with pytest.raises(IntegrityError):
        User.objects.create_user(email="DUP2@EXAMPLE.COM", password="another-password-2")


def test_create_user_without_email_rejected():
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="a-strong-password-1")


def test_create_superuser():
    admin = User.objects.create_superuser(email="root@example.com", password="a-strong-password-1")

    assert admin.is_staff is True
    assert admin.is_superuser is True
    # Model invariant: a Django superuser is always the CRM's SUPER_ADMIN role.
    assert admin.role == User.Role.SUPER_ADMIN


def test_create_superuser_rejects_is_staff_false():
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="bad1@example.com", password="a-strong-password-1", is_staff=False)


def test_create_superuser_rejects_is_superuser_false():
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="bad2@example.com", password="a-strong-password-1", is_superuser=False)


def test_create_user_rejects_is_superuser_true():
    """create_user() must never be able to mint Django superuser/staff access."""
    with pytest.raises(ValueError):
        User.objects.create_user(email="sneaky@example.com", password="a-strong-password-1", is_superuser=True)


def test_create_user_rejects_is_staff_true():
    with pytest.raises(ValueError):
        User.objects.create_user(email="sneaky2@example.com", password="a-strong-password-1", is_staff=True)


def test_username_field_is_email():
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == []


def test_default_role_for_normal_user_is_employee():
    user = User.objects.create_user(email="new-hire@example.com", password="a-strong-password-1")

    assert user.role == User.Role.EMPLOYEE


def test_role_can_be_set_to_manager_or_super_admin_without_django_privileges():
    """The role field is an independent identity label from is_staff/is_superuser."""
    manager = User.objects.create_user(
        email="manager@example.com", password="a-strong-password-1", role=User.Role.MANAGER
    )

    assert manager.role == User.Role.MANAGER
    assert manager.is_staff is False
    assert manager.is_superuser is False


def test_str_returns_email():
    user = User.objects.create_user(email="whoami@example.com", password="a-strong-password-1")

    assert str(user) == "whoami@example.com"
