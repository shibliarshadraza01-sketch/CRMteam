"""CP5 tests: device session tracking (login/refresh/logout integration,
the sessions list/revoke/logout-all endpoints, and cross-user isolation).

Requires a real database connection (pytest-django creates a throwaway
PostgreSQL test database). Cannot run until PostgreSQL is available — see
BACKEND_PROGRESS.md CP5 for the current blocker/status. Mirrors the same
honest-blocker pattern established in CP2/CP3/CP4.

Pure, DB-free CP5 logic (user-agent parsing, IP extraction) lives in
test_session_utils.py instead, and does actually run/pass today.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserSession

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _reset_throttle_cache():
    """LoginView is rate-limited (final-completion-pass: ScopedRateThrottle,
    scope "login") — this file's ``_login()`` helper is called dozens of
    times across its tests, sharing one LocMemCache counter without this.
    Same pattern as test_auth.py's identical fixture.
    """
    cache.clear()
    yield
    cache.clear()

User = get_user_model()

LOGIN_URL = "/api/v1/auth/login/"
REFRESH_URL = "/api/v1/auth/refresh/"
LOGOUT_URL = "/api/v1/auth/logout/"
ME_URL = "/api/v1/auth/me/"
VERIFY_URL = "/api/v1/auth/super-admin/verify/"
SESSIONS_URL = "/api/v1/auth/sessions/"
LOGOUT_ALL_URL = "/api/v1/auth/logout-all/"

VALID_PASSWORD = "a-strong-password-1"
VALID_CODE = "a-strong-access-code-1"

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
FIREFOX_UA = "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def employee():
    return User.objects.create_user(email="employee@example.com", password=VALID_PASSWORD, role=User.Role.EMPLOYEE)


@pytest.fixture
def other_employee():
    return User.objects.create_user(email="other@example.com", password=VALID_PASSWORD, role=User.Role.EMPLOYEE)


@pytest.fixture
def super_admin():
    user = User.objects.create_user(email="root@example.com", password=VALID_PASSWORD, role=User.Role.SUPER_ADMIN)
    user.set_access_code(VALID_CODE)
    user.save()
    return user


def _login(client, email, password=VALID_PASSWORD, user_agent=CHROME_UA):
    return client.post(LOGIN_URL, {"email": email, "password": password}, HTTP_USER_AGENT=user_agent)


# --------------------------------------------------------------------------
# Login creates a session
# --------------------------------------------------------------------------


def test_login_creates_a_session(client, employee):
    assert UserSession.objects.filter(user=employee).count() == 0

    _login(client, employee.email)

    assert UserSession.objects.filter(user=employee).count() == 1


def test_login_session_captures_device_metadata(client, employee):
    _login(client, employee.email, user_agent=CHROME_UA)

    session = UserSession.objects.get(user=employee)
    assert session.browser == "Chrome"
    assert session.operating_system == "Windows"
    assert session.device_type == UserSession.DeviceType.DESKTOP
    assert session.device_name == "Chrome on Windows"
    assert session.is_active is True


def test_login_session_tracks_the_refresh_token_jti(client, employee):
    login = _login(client, employee.email).json()

    refresh_jti = RefreshToken(login["refresh"]).payload["jti"]
    session = UserSession.objects.get(user=employee)

    assert session.refresh_token_jti == refresh_jti


def test_multiple_devices_create_separate_sessions(client, employee):
    _login(client, employee.email, user_agent=CHROME_UA)
    _login(client, employee.email, user_agent=FIREFOX_UA)

    sessions = UserSession.objects.filter(user=employee, is_active=True)
    assert sessions.count() == 2
    browsers = set(sessions.values_list("browser", flat=True))
    assert browsers == {"Chrome", "Firefox"}


def test_super_admin_verify_creates_a_session(client, super_admin):
    challenge = _login(client, super_admin.email).json()["challenge"]

    assert UserSession.objects.filter(user=super_admin).count() == 0

    client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE}, HTTP_USER_AGENT=CHROME_UA)

    assert UserSession.objects.filter(user=super_admin).count() == 1


def test_super_admin_primary_login_alone_does_not_create_a_session(client, super_admin):
    """Only a successful /super-admin/verify/ issues tokens; the challenge
    step itself must not create a session.
    """
    _login(client, super_admin.email)

    assert UserSession.objects.filter(user=super_admin).count() == 0


# --------------------------------------------------------------------------
# Refresh updates the session
# --------------------------------------------------------------------------


def test_refresh_updates_last_used_at(client, employee):
    login = _login(client, employee.email).json()
    session = UserSession.objects.get(user=employee)
    original_last_used = session.last_used_at

    client.post(REFRESH_URL, {"refresh": login["refresh"]})

    session.refresh_from_db()
    assert session.last_used_at > original_last_used


def test_refresh_rotates_the_tracked_jti_not_a_new_session(client, employee):
    """Rotation is enabled (CP3) — refreshing must update the EXISTING
    session's tracked JTI, not create a second session row.
    """
    login = _login(client, employee.email).json()
    assert UserSession.objects.filter(user=employee).count() == 1

    refreshed = client.post(REFRESH_URL, {"refresh": login["refresh"]}).json()

    assert UserSession.objects.filter(user=employee).count() == 1
    session = UserSession.objects.get(user=employee)
    new_jti = RefreshToken(refreshed["refresh"]).payload["jti"]
    assert session.refresh_token_jti == new_jti
    # verify=False: login["refresh"] was already rotated (and, since
    # BLACKLIST_AFTER_ROTATION=True, blacklisted) by the refresh call
    # above — RefreshToken(...) with default verification would raise
    # TokenError reading it back. Decoding its payload without
    # re-verifying is fine here: this is just extracting the OLD jti for
    # comparison, not authenticating a request with it.
    old_jti = RefreshToken(login["refresh"], verify=False).payload["jti"]
    assert session.refresh_token_jti != old_jti


def test_refresh_with_expired_or_invalid_token_does_not_touch_sessions(client, employee):
    login = _login(client, employee.email).json()
    session = UserSession.objects.get(user=employee)
    original_last_used = session.last_used_at

    response = client.post(REFRESH_URL, {"refresh": "not-a-real-token"})

    assert response.status_code == 401
    session.refresh_from_db()
    assert session.last_used_at == original_last_used


# --------------------------------------------------------------------------
# Logout deactivates the session
# --------------------------------------------------------------------------


def test_logout_deactivates_the_session(client, employee):
    login = _login(client, employee.email).json()

    client.post(LOGOUT_URL, {"refresh": login["refresh"]})

    session = UserSession.objects.get(user=employee)
    assert session.is_active is False


def test_logout_blacklists_the_refresh_token(client, employee):
    login = _login(client, employee.email).json()
    jti = RefreshToken(login["refresh"]).payload["jti"]

    client.post(LOGOUT_URL, {"refresh": login["refresh"]})

    outstanding = OutstandingToken.objects.get(jti=jti)
    assert BlacklistedToken.objects.filter(token=outstanding).exists()


def test_logout_does_not_delete_the_session_row(client, employee):
    login = _login(client, employee.email).json()

    client.post(LOGOUT_URL, {"refresh": login["refresh"]})

    assert UserSession.objects.filter(user=employee).count() == 1  # still there, just inactive


# --------------------------------------------------------------------------
# GET /sessions/
# --------------------------------------------------------------------------


def test_list_sessions_requires_authentication(client):
    response = client.get(SESSIONS_URL)

    assert response.status_code == 401


def test_list_sessions_returns_only_active_sessions(client, employee):
    login1 = _login(client, employee.email, user_agent=CHROME_UA).json()
    login2 = _login(client, employee.email, user_agent=FIREFOX_UA).json()
    client.post(LOGOUT_URL, {"refresh": login1["refresh"]})

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login2['access']}")
    response = client.get(SESSIONS_URL)

    assert response.status_code == 200
    body = response.json()
    results = body["results"] if isinstance(body, dict) and "results" in body else body
    assert len(results) == 1
    assert results[0]["browser"] == "Firefox"


def test_list_sessions_marks_current_session(client, employee):
    login = _login(client, employee.email).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    response = client.get(SESSIONS_URL)

    body = response.json()
    results = body["results"] if isinstance(body, dict) and "results" in body else body
    assert results[0]["current_session"] is True


def test_list_sessions_response_never_contains_sensitive_fields(client, employee):
    login = _login(client, employee.email).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    response = client.get(SESSIONS_URL)

    body_text = response.content.decode().lower()
    assert "refresh_token_jti" not in body_text
    assert "jti" not in body_text
    assert "password" not in body_text
    assert "access_code" not in body_text
    assert login["refresh"] not in response.content.decode()
    assert login["access"] not in response.content.decode()


def test_sessions_only_ever_show_the_caller_s_own(client, employee, other_employee):
    _login(client, employee.email)
    login_other = _login(client, other_employee.email).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_other['access']}")
    response = client.get(SESSIONS_URL)

    body = response.json()
    results = body["results"] if isinstance(body, dict) and "results" in body else body
    assert len(results) == 1
    assert UserSession.objects.get(pk=results[0]["id"]).user_id == other_employee.id


# --------------------------------------------------------------------------
# DELETE /sessions/<id>/
# --------------------------------------------------------------------------


def test_delete_session_requires_authentication(client, employee):
    login = _login(client, employee.email).json()
    session_id = UserSession.objects.get(user=employee).id

    client.credentials()  # no auth
    response = client.delete(f"{SESSIONS_URL}{session_id}/")

    assert response.status_code == 401


def test_delete_own_session_revokes_it(client, employee):
    login = _login(client, employee.email, user_agent=CHROME_UA).json()
    login2 = _login(client, employee.email, user_agent=FIREFOX_UA).json()
    target_session = UserSession.objects.get(refresh_token_jti=RefreshToken(login2["refresh"]).payload["jti"])

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    response = client.delete(f"{SESSIONS_URL}{target_session.id}/")

    assert response.status_code == 204
    target_session.refresh_from_db()
    assert target_session.is_active is False


def test_delete_session_blacklists_its_refresh_token(client, employee):
    login = _login(client, employee.email).json()
    session = UserSession.objects.get(user=employee)

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    client.delete(f"{SESSIONS_URL}{session.id}/")

    refresh_after_revoke = client.post(REFRESH_URL, {"refresh": login["refresh"]})
    assert refresh_after_revoke.status_code == 401


def test_delete_another_users_session_is_denied(client, employee, other_employee):
    login_other = _login(client, other_employee.email).json()
    other_session = UserSession.objects.get(user=other_employee)

    login_me = _login(client, employee.email).json()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_me['access']}")
    response = client.delete(f"{SESSIONS_URL}{other_session.id}/")

    assert response.status_code == 404  # not found, not even a distinguishable 403
    other_session.refresh_from_db()
    assert other_session.is_active is True  # untouched


def test_delete_nonexistent_session_returns_404(client, employee):
    login = _login(client, employee.email).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    response = client.delete(f"{SESSIONS_URL}999999/")

    assert response.status_code == 404


# --------------------------------------------------------------------------
# POST /logout-all/
# --------------------------------------------------------------------------


def test_logout_all_requires_authentication(client):
    response = client.post(LOGOUT_ALL_URL)

    assert response.status_code == 401


def test_logout_all_revokes_other_sessions_but_not_current(client, employee):
    login_a = _login(client, employee.email, user_agent=CHROME_UA).json()
    login_b = _login(client, employee.email, user_agent=FIREFOX_UA).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_a['access']}")
    response = client.post(LOGOUT_ALL_URL)

    assert response.status_code == 200
    assert response.json()["revoked"] == 1

    # verify=False: login_b's refresh token was just revoked (blacklisted)
    # by the logout-all call above — see the note on the identical pattern
    # in test_refresh_rotates_the_tracked_jti_not_a_new_session.
    session_a = UserSession.objects.get(refresh_token_jti=RefreshToken(login_a["refresh"], verify=False).payload["jti"])
    session_b = UserSession.objects.get(refresh_token_jti=RefreshToken(login_b["refresh"], verify=False).payload["jti"])
    assert session_a.is_active is True  # current session survives
    assert session_b.is_active is False  # the other one is revoked


def test_logout_all_blacklists_revoked_refresh_tokens(client, employee):
    login_a = _login(client, employee.email, user_agent=CHROME_UA).json()
    login_b = _login(client, employee.email, user_agent=FIREFOX_UA).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_a['access']}")
    client.post(LOGOUT_ALL_URL)

    still_works = client.post(REFRESH_URL, {"refresh": login_a["refresh"]})
    now_blacklisted = client.post(REFRESH_URL, {"refresh": login_b["refresh"]})

    assert still_works.status_code == 200
    assert now_blacklisted.status_code == 401


def test_logout_all_only_affects_the_calling_user(client, employee, other_employee):
    login_me = _login(client, employee.email).json()
    login_other = _login(client, other_employee.email).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_me['access']}")
    response = client.post(LOGOUT_ALL_URL)

    assert response.json()["revoked"] == 0  # only session was the current one, nothing else to revoke
    other_session = UserSession.objects.get(user=other_employee)
    assert other_session.is_active is True


# --------------------------------------------------------------------------
# Cross-user access denied (broader sweep)
# --------------------------------------------------------------------------


def test_employee_cannot_see_managers_sessions(client, employee):
    manager = User.objects.create_user(email="mgr@example.com", password=VALID_PASSWORD, role=User.Role.MANAGER)
    _login(client, manager.email)
    login_employee = _login(client, employee.email).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_employee['access']}")
    response = client.get(SESSIONS_URL)

    body = response.json()
    results = body["results"] if isinstance(body, dict) and "results" in body else body
    assert all(UserSession.objects.get(pk=r["id"]).user_id == employee.id for r in results)


def test_super_admin_cannot_bypass_session_ownership(client, super_admin, employee):
    """CP5 rule: 'No admin shortcuts' — even SUPER_ADMIN only ever sees/revokes
    their own sessions through these endpoints.
    """
    _login(client, employee.email)
    challenge = _login(client, super_admin.email).json()["challenge"]
    admin_tokens = client.post(VERIFY_URL, {"challenge": challenge, "access_code": VALID_CODE}).json()

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_tokens['access']}")
    list_response = client.get(SESSIONS_URL)
    body = list_response.json()
    results = body["results"] if isinstance(body, dict) and "results" in body else body
    assert all(UserSession.objects.get(pk=r["id"]).user_id == super_admin.id for r in results)

    employee_session = UserSession.objects.get(user=employee)
    delete_response = client.delete(f"{SESSIONS_URL}{employee_session.id}/")
    assert delete_response.status_code == 404
