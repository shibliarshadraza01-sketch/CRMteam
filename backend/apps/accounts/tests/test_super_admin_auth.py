"""CP4 tests: the Super Admin secondary-authentication HTTP flow.

Requires a real database connection (pytest-django creates a throwaway
PostgreSQL test database). Cannot run until PostgreSQL is available — see
BACKEND_PROGRESS.md CP4 for the current blocker/status. Mirrors the same
honest-blocker pattern established in CP2/CP3.

Pure model/signing-level CP4 logic that does NOT need a database lives in
test_super_admin_access_code.py instead, and does actually run/pass today.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.challenge import issue_super_admin_challenge

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture(autouse=True)
def _reset_throttle_cache():
    """SuperAdminVerifyView is rate-limited via DRF's ScopedRateThrottle
    (config/settings/base.py, scope "super_admin_verify"), which counts
    requests in Django's default cache (LocMemCache — in-process, shared for
    the whole test run, not reset between tests). Without this, this file's
    ~13 tests against VERIFY_URL share one 5/min counter and start getting
    throttled (403) partway through the file regardless of what each test
    actually asserts — a test-isolation gap, not a production behavior
    change. Production's LocMemCache correctly persists between real
    requests; only the test suite needs its own state wiped per test.
    """
    cache.clear()
    yield
    cache.clear()

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"
VERIFY_URL = "/api/v1/auth/super-admin/verify/"

VALID_PASSWORD = "a-strong-password-1"
VALID_CODE = "a-strong-access-code-1"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def employee():
    return User.objects.create_user(email="employee@example.com", password=VALID_PASSWORD, role=User.Role.EMPLOYEE)


@pytest.fixture
def manager():
    return User.objects.create_user(email="manager@example.com", password=VALID_PASSWORD, role=User.Role.MANAGER)


@pytest.fixture
def super_admin():
    user = User.objects.create_user(email="root@example.com", password=VALID_PASSWORD, role=User.Role.SUPER_ADMIN)
    user.set_access_code(VALID_CODE)
    user.save()
    return user


# --------------------------------------------------------------------------
# NORMAL USERS — unaffected by CP4
# --------------------------------------------------------------------------


def test_employee_login_unchanged(client, employee):
    response = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert "access" in body and "refresh" in body
    assert "secondary_verification_required" not in body
    assert body["user"]["role"] == "EMPLOYEE"


def test_manager_login_unchanged(client, manager):
    response = client.post(LOGIN_URL, {"email": "manager@example.com", "password": VALID_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert "access" in body and "refresh" in body
    assert "secondary_verification_required" not in body
    assert body["user"]["role"] == "MANAGER"


@pytest.mark.parametrize("role_fixture", ["employee", "manager"])
def test_normal_users_never_receive_a_challenge(client, role_fixture, request):
    user = request.getfixturevalue(role_fixture)
    response = client.post(LOGIN_URL, {"email": user.email, "password": VALID_PASSWORD})

    assert "challenge" not in response.json()


@pytest.mark.parametrize("role_fixture", ["employee", "manager"])
def test_normal_user_tokens_work_immediately_at_me(client, role_fixture, request):
    user = request.getfixturevalue(role_fixture)
    login = client.post(LOGIN_URL, {"email": user.email, "password": VALID_PASSWORD}).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    response = client.get(ME_URL)

    assert response.status_code == 200
    assert response.json()["role"] == user.role


# --------------------------------------------------------------------------
# SUPER ADMIN — primary login
# --------------------------------------------------------------------------


def test_super_admin_primary_login_does_not_return_jwt_pair(client, super_admin):
    response = client.post(LOGIN_URL, {"email": "root@example.com", "password": VALID_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert "access" not in body
    assert "refresh" not in body


def test_super_admin_primary_login_indicates_secondary_required(client, super_admin):
    response = client.post(LOGIN_URL, {"email": "root@example.com", "password": VALID_PASSWORD})

    body = response.json()
    assert body["secondary_verification_required"] is True
    assert "challenge" in body and body["challenge"]


def test_super_admin_challenge_does_not_expose_access_code(client, super_admin):
    response = client.post(LOGIN_URL, {"email": "root@example.com", "password": VALID_PASSWORD})

    body_text = response.content.decode()
    assert VALID_CODE not in body_text
    assert "access_code" not in body_text
    assert super_admin.super_admin_access_code_hash not in body_text


def test_super_admin_challenge_cannot_authenticate_me(client, super_admin):
    login = client.post(LOGIN_URL, {"email": "root@example.com", "password": VALID_PASSWORD}).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['challenge']}")
    response = client.get(ME_URL)

    assert response.status_code == 401


def test_super_admin_wrong_primary_password_fails_normally(client, super_admin):
    response = client.post(LOGIN_URL, {"email": "root@example.com", "password": "wrong-password"})

    assert response.status_code == 401
    assert "challenge" not in response.json()


def test_inactive_super_admin_cannot_begin_authentication(client):
    User.objects.create_user(
        email="inactive-admin@example.com", password=VALID_PASSWORD, role=User.Role.SUPER_ADMIN, is_active=False
    )

    response = client.post(LOGIN_URL, {"email": "inactive-admin@example.com", "password": VALID_PASSWORD})

    assert response.status_code == 401


# --------------------------------------------------------------------------
# VERIFY ENDPOINT
# --------------------------------------------------------------------------


def _login_challenge(client, email=None):
    login = client.post(LOGIN_URL, {"email": email or "root@example.com", "password": VALID_PASSWORD}).json()
    return login["challenge"]


def test_verify_valid_challenge_and_code_succeeds(client, super_admin):
    challenge = _login_challenge(client)

    response = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE})

    assert response.status_code == 200


def test_verify_success_returns_access_and_refresh(client, super_admin):
    challenge = _login_challenge(client)

    body = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE}).json()

    assert "access" in body and body["access"]
    assert "refresh" in body and body["refresh"]
    assert body["user"]["role"] == "SUPER_ADMIN"


def test_verify_issued_jwt_works_with_me(client, super_admin):
    challenge = _login_challenge(client)
    tokens = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE}).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    response = client.get(ME_URL)

    assert response.status_code == 200
    assert response.json()["email"] == "root@example.com"


def test_verify_wrong_access_code_fails(client, super_admin):
    challenge = _login_challenge(client)

    response = client.post(VERIFY_URL, {"challenge": challenge, "access_code": "wrong-code"})

    assert response.status_code == 401
    assert "access" not in response.json()


def test_verify_missing_challenge_fails(client, super_admin):
    response = client.post(VERIFY_URL, {"access_code": VALID_CODE})

    assert response.status_code == 400


def test_verify_missing_access_code_fails(client, super_admin):
    challenge = _login_challenge(client)

    response = client.post(VERIFY_URL, {"challenge": challenge})

    assert response.status_code == 400


def test_verify_malformed_challenge_fails(client):
    response = client.post(VERIFY_URL, {"challenge": "not-a-real-challenge", "access_code": VALID_CODE})

    assert response.status_code == 401


def test_verify_expired_challenge_fails(client, super_admin, settings):
    settings.SUPER_ADMIN_CHALLENGE_TTL_SECONDS = 0
    challenge = _login_challenge(client)

    response = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE})

    assert response.status_code == 401


def test_verify_inactive_user_challenge_fails(client, super_admin):
    challenge = _login_challenge(client)
    super_admin.is_active = False
    super_admin.save()

    response = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE})

    assert response.status_code == 401


def test_verify_fails_after_role_changed_away_from_super_admin(client, super_admin):
    challenge = _login_challenge(client)
    super_admin.role = User.Role.MANAGER
    super_admin.save()

    response = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE})

    assert response.status_code == 401


def test_verify_rejects_a_forged_challenge_for_a_normal_user(client, employee):
    """Defense in depth: even a validly-signed challenge naming a non-Super-Admin
    user (which normal login flow never issues — see the LoginView branch)
    must still be rejected by the verify serializer's own role check.
    """
    challenge = issue_super_admin_challenge(employee)

    response = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE})

    assert response.status_code == 401


def test_verify_super_admin_without_configured_code_fails_safely(client):
    user = User.objects.create_user(email="nocode@example.com", password=VALID_PASSWORD, role=User.Role.SUPER_ADMIN)
    challenge = issue_super_admin_challenge(user)

    response = client.post(VERIFY_URL, {"challenge": challenge, "access_code": "anything"})

    assert response.status_code == 401


def test_verify_response_never_contains_secrets(client, super_admin):
    challenge = _login_challenge(client)

    response = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE})

    body_text = response.content.decode().lower()
    assert "password" not in body_text
    assert VALID_CODE.lower() not in body_text
    assert super_admin.super_admin_access_code_hash.lower() not in body_text


# --------------------------------------------------------------------------
# TOKEN SEPARATION
# --------------------------------------------------------------------------


def test_challenge_cannot_be_used_as_bearer_access_token(client, super_admin):
    challenge = _login_challenge(client)

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {challenge}")
    response = client.get(ME_URL)

    assert response.status_code == 401


def test_challenge_cannot_be_used_to_logout(client, super_admin):
    """A challenge is not a refresh token — /logout/ must reject it, not
    silently "succeed" at blacklisting something that was never a real
    SimpleJWT token in the first place.
    """
    challenge = _login_challenge(client)

    response = client.post(LOGOUT_URL, {"refresh": challenge})

    assert response.status_code == 400


def test_challenge_cannot_be_used_at_refresh(client, super_admin):
    challenge = _login_challenge(client)

    response = client.post(REFRESH_URL, {"refresh": challenge})

    assert response.status_code == 401


def test_access_token_cannot_be_used_as_challenge(client, employee):
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()

    response = client.post(VERIFY_URL, {"challenge": login["access"], "access_code": VALID_CODE})

    assert response.status_code == 401


def test_refresh_token_cannot_be_used_as_challenge(client, employee):
    login = client.post(LOGIN_URL, {"email": "employee@example.com", "password": VALID_PASSWORD}).json()

    response = client.post(VERIFY_URL, {"challenge": login["refresh"], "access_code": VALID_CODE})

    assert response.status_code == 401


# --------------------------------------------------------------------------
# Full lifecycle + refresh/logout continue working after verification
# --------------------------------------------------------------------------


def test_super_admin_full_lifecycle_refresh_and_logout(client, super_admin):
    challenge = _login_challenge(client)
    tokens = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE}).json()

    # refresh works like any other verified user's tokens
    refreshed = client.post(REFRESH_URL, {"refresh": tokens["refresh"]})
    assert refreshed.status_code == 200

    # logout blacklists the (rotated) refresh token
    new_refresh = refreshed.json()["refresh"]
    logout = client.post(LOGOUT_URL, {"refresh": new_refresh})
    assert logout.status_code == 200

    # and it can no longer be refreshed afterward
    rejected = client.post(REFRESH_URL, {"refresh": new_refresh})
    assert rejected.status_code == 401


# --------------------------------------------------------------------------
# Model invariant: role demotion at save-time clears a stale hash
# --------------------------------------------------------------------------


def test_role_demotion_clears_hash_on_save(super_admin):
    assert super_admin.super_admin_access_code_hash

    super_admin.role = User.Role.EMPLOYEE
    super_admin.save()
    super_admin.refresh_from_db()

    assert super_admin.super_admin_access_code_hash == ""
