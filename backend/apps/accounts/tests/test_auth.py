"""CP3 tests: JWT authentication (login, refresh, /me, logout).

Requires a real database connection (pytest-django creates a throwaway
PostgreSQL test database, and SimpleJWT's blacklist app writes to real
tables). Cannot run until PostgreSQL is available — see BACKEND_PROGRESS.md
CP3 for the current blocker/status. Mirrors the same honest-blocker pattern
established in CP2's apps/accounts/tests/test_user_model.py.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture(autouse=True)
def _reset_throttle_cache():
    """LoginView is now rate-limited (final-completion-pass: ScopedRateThrottle,
    scope "login", see config/settings/base.py) — same LocMemCache
    test-isolation need as test_super_admin_auth.py's identical fixture.
    Without this, this file's ~20 tests against LOGIN_URL share one 10/min
    counter and start getting throttled partway through the file.
    """
    cache.clear()
    yield
    cache.clear()


LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"

VALID_PASSWORD = "a-strong-password-1"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def employee():
    return User.objects.create_user(email="employee@example.com", password=VALID_PASSWORD, role=User.Role.EMPLOYEE)


# --------------------------------------------------------------------------
# LOGIN
# --------------------------------------------------------------------------


def test_login_valid_credentials(client, employee):
    response = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert "access" in body and body["access"]
    assert "refresh" in body and body["refresh"]
    assert body["user"]["email"] == "employee@example.com"
    assert body["user"]["role"] == "EMPLOYEE"


def test_login_wrong_password(client, employee):
    response = client.post(LOGIN_URL, {"email": "employee@example.com", "password": "wrong-password"})

    assert response.status_code == 401
    assert "password" not in response.json()


def test_login_nonexistent_email(client):
    response = client.post(LOGIN_URL, {"email": "nobody@example.com", "password": VALID_PASSWORD})

    assert response.status_code == 401


def test_login_error_message_does_not_reveal_which_field_was_wrong(client, employee):
    """Wrong password and nonexistent email must produce the identical error body."""
    wrong_password = client.post(LOGIN_URL, {"email": "employee@example.com", "password": "wrong"})
    nonexistent = client.post(LOGIN_URL, {"email": "nobody@example.com", "password": VALID_PASSWORD})

    assert wrong_password.status_code == nonexistent.status_code == 401
    assert wrong_password.json() == nonexistent.json()


def test_login_inactive_user_rejected(client):
    User.objects.create_user(email="inactive@example.com", password=VALID_PASSWORD, is_active=False)

    response = client.post(LOGIN_URL, {"email": "inactive@example.com", "password": VALID_PASSWORD})

    assert response.status_code == 401


def test_login_missing_email(client):
    response = client.post(LOGIN_URL, {"password": VALID_PASSWORD})

    assert response.status_code == 400


def test_login_missing_password(client):
    response = client.post(LOGIN_URL, {"email": "employee@example.com"})

    assert response.status_code == 400


def test_login_malformed_email(client):
    response = client.post(LOGIN_URL, {"email": "not-an-email", "password": VALID_PASSWORD})

    assert response.status_code == 400


def test_login_response_never_contains_password_or_hash(client, employee):
    response = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD})

    body_text = response.content.decode()
    assert "password" not in body_text.lower()
    assert employee.password not in body_text


# --------------------------------------------------------------------------
# TOKENS (refresh)
# --------------------------------------------------------------------------


def test_refresh_returns_new_access_token(client, employee):
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()

    response = client.post(REFRESH_URL, {"refresh": login["refresh"]})

    assert response.status_code == 200
    assert "access" in response.json()
    # Rotation is enabled, so a fresh refresh token is also issued.
    assert "refresh" in response.json()
    assert response.json()["access"] != login["access"]


def test_refresh_invalid_token_rejected(client):
    response = client.post(REFRESH_URL, {"refresh": "this-is-not-a-real-token"})

    assert response.status_code == 401


def test_refresh_malformed_token_rejected(client):
    response = client.post(REFRESH_URL, {"refresh": "###"})

    assert response.status_code == 401


def test_refresh_missing_token_rejected(client):
    response = client.post(REFRESH_URL, {})

    assert response.status_code == 400


def test_refresh_blacklisted_token_rejected(client, employee):
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()
    client.post(LOGOUT_URL, {"refresh": login["refresh"]})

    response = client.post(REFRESH_URL, {"refresh": login["refresh"]})

    assert response.status_code == 401


def test_rotated_refresh_token_cannot_be_reused(client, employee):
    """ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION: a refresh token is single-use."""
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()
    first_refresh = client.post(REFRESH_URL, {"refresh": login["refresh"]})
    assert first_refresh.status_code == 200

    # Reusing the *original* refresh token (now rotated away) must fail.
    second_attempt = client.post(REFRESH_URL, {"refresh": login["refresh"]})

    assert second_attempt.status_code == 401


def test_refresh_token_rejected_by_protected_endpoint(client, employee):
    """A refresh token must not work as a Bearer access token."""
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['refresh']}")
    response = client.get(ME_URL)

    assert response.status_code == 401


# --------------------------------------------------------------------------
# CURRENT USER (/me/)
# --------------------------------------------------------------------------


def test_me_with_valid_access_token(client, employee):
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    response = client.get(ME_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == employee.id
    assert body["email"] == "employee@example.com"
    assert body["first_name"] == employee.first_name
    assert body["last_name"] == employee.last_name
    assert body["role"] == "EMPLOYEE"


def test_me_without_token_rejected(client):
    response = client.get(ME_URL)

    assert response.status_code == 401


def test_me_with_malformed_token_rejected(client):
    client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")
    response = client.get(ME_URL)

    assert response.status_code == 401


def test_me_response_has_no_sensitive_fields(client, employee):
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    response = client.get(ME_URL)

    body = response.json()
    assert set(body.keys()) == {"id", "email", "first_name", "last_name", "role"}


# --------------------------------------------------------------------------
# LOGOUT
# --------------------------------------------------------------------------


def test_logout_valid(client, employee):
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()

    response = client.post(LOGOUT_URL, {"refresh": login["refresh"]})

    assert response.status_code == 200


def test_logout_makes_refresh_token_unusable(client, employee):
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()
    client.post(LOGOUT_URL, {"refresh": login["refresh"]})

    response = client.post(REFRESH_URL, {"refresh": login["refresh"]})

    assert response.status_code == 401


def test_logout_missing_refresh_token(client):
    response = client.post(LOGOUT_URL, {})

    assert response.status_code == 400


def test_logout_invalid_refresh_token(client):
    response = client.post(LOGOUT_URL, {"refresh": "not-a-real-token"})

    assert response.status_code == 400


def test_logout_already_blacklisted_token(client, employee):
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()
    client.post(LOGOUT_URL, {"refresh": login["refresh"]})

    response = client.post(LOGOUT_URL, {"refresh": login["refresh"]})

    assert response.status_code == 400


# --------------------------------------------------------------------------
# USER TYPES
# --------------------------------------------------------------------------


@pytest.mark.parametrize("role", [User.Role.EMPLOYEE, User.Role.MANAGER, User.Role.SUPER_ADMIN])
def test_login_works_for_every_role(client, role):
    """Every role authenticates through the identical CP3 email/password
    validation step.

    CP4 (built after this test was first written) changed what a
    SUPER_ADMIN's successful primary-credential check actually returns:
    not tokens directly, but a `secondary_verification_required` challenge
    — see LoginView and test_super_admin_auth.py for the full flow this
    challenge feeds into. Updated here to assert the real CP4 shape rather
    than the pre-CP4 placeholder this parametrize case predates.
    """
    user = User.objects.create_user(email=f"{role.lower()}@example.com", password=VALID_PASSWORD, role=role)

    response = client.post(LOGIN_URL, {"email": user.email, "password": VALID_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    if role == User.Role.SUPER_ADMIN:
        assert body["secondary_verification_required"] is True
        assert body["challenge"]
    else:
        assert body["user"]["role"] == role
