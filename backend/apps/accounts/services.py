"""CP5: the database-touching half of session management.

Everything in apps/accounts/session_utils.py is a pure function; everything
here reads or writes UserSession/OutstandingToken/BlacklistedToken rows. Kept
in this separate, narrowly-focused module (STEP 9 of CP3's own instructions
established this "service functions, keep them narrow" convention) rather
than folded into views.py, so the session lifecycle can be understood and
tested independently of any particular endpoint.

Every function here is called from exactly one place in views.py — see
BACKEND_LEARNING_GUIDE.md CP5, "implementation walkthrough", for the full
call graph.
"""
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import UserSession
from .session_utils import build_device_name, get_client_ip, parse_user_agent

User = get_user_model()


def create_managed_user(email, password, *, role, first_name="", last_name=""):
    """Create a user account via the admin-facing Users management API
    (final-completion-pass — see ``views.py``'s ``UserViewSet``).

    Thin wrapper around ``User.objects.create_user()`` (CP2), kept as a
    service function per this project's own convention: one place for a
    future rule (e.g. "a Manager can only create Employees, not other
    Managers") to live without touching the view. ``role=SUPER_ADMIN`` is
    permitted — the model's own ``save()`` invariant (see models.py)
    doesn't require a secondary access code to exist for a SUPER_ADMIN
    row; it just means that account cannot complete a real login until
    ``set_access_code()`` is used to configure one (no API surface for
    that exists yet — a deliberate, documented gap, not an oversight).
    """
    return User.objects.create_user(
        email=email, password=password, role=role, first_name=first_name, last_name=last_name
    )


def deactivate_user(user):
    """Deactivate ``user`` (``is_active=False``) — the only "removal"
    action the Users management API exposes. Never a real delete: a
    User is referenced by FK from too much of the rest of the schema
    (owned records, audit entries, sessions) for a hard delete to ever
    be a safe admin action; deactivation is reversible and is what
    actually blocks login (``ModelBackend.user_can_authenticate()``
    already excludes inactive users).
    """
    user.is_active = False
    user.save(update_fields=["is_active"])
    return user


def activate_user(user):
    """Reverse of ``deactivate_user()``."""
    user.is_active = True
    user.save(update_fields=["is_active"])
    return user


def create_session(user, refresh_token, request):
    """Create a UserSession row for a freshly-issued refresh token.

    Called once, immediately after RefreshToken.for_user(user) — see
    views.py's _issue_token_pair_response(), the single shared path both
    ordinary login and CP4's Super Admin verify use to issue tokens. `expires_at`
    is read directly from the token's own "exp" claim, so it is always exactly
    correct relative to SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] without
    recomputing that duration separately here.
    """
    jti = refresh_token.payload.get("jti")
    exp_timestamp = refresh_token.payload.get("exp")
    expires_at = (
        timezone.datetime.fromtimestamp(exp_timestamp, tz=timezone.get_current_timezone())
        if exp_timestamp
        else timezone.now()
    )

    user_agent_string = request.META.get("HTTP_USER_AGENT", "") if request is not None else ""
    device_type, browser, operating_system = parse_user_agent(user_agent_string)

    return UserSession.objects.create(
        user=user,
        refresh_token_jti=jti,
        device_name=build_device_name(browser, operating_system),
        device_type=device_type,
        browser=browser,
        operating_system=operating_system,
        ip_address=get_client_ip(request) if request is not None else None,
        user_agent=user_agent_string,
        expires_at=expires_at,
    )


def touch_session_on_refresh(old_jti, new_jti, new_expires_at=None):
    """Update an existing session in place when its refresh token is renewed.

    Deliberately does NOT create a new UserSession row — a refresh is a
    continuation of the same session, not a new login. If rotation is
    enabled (SIMPLE_JWT["ROTATE_REFRESH_TOKENS"], as configured since CP3),
    `new_jti` differs from `old_jti` and the session's tracked JTI moves
    forward with it, so a later revoke/logout-all still finds the right row.
    A no-op (0 rows affected) if no active session matches `old_jti` — this
    can legitimately happen for tokens issued before CP5 existed, and must
    not raise.
    """
    if not old_jti:
        return
    updates = {"refresh_token_jti": new_jti or old_jti, "last_used_at": timezone.now()}
    if new_expires_at is not None:
        updates["expires_at"] = new_expires_at
    UserSession.objects.filter(refresh_token_jti=old_jti, is_active=True).update(**updates)


def blacklist_by_jti(jti):
    """Blacklist the refresh token identified by `jti`, if SimpleJWT still
    has an OutstandingToken record for it.

    Every RefreshToken issued via for_user() automatically gets an
    OutstandingToken row the moment it is created (this is
    rest_framework_simplejwt.token_blacklist's own behavior once the app is
    installed — see CP3). Blacklisting therefore never needs the raw token
    string, only its jti — which is exactly the one piece of token material
    UserSession is allowed to store (see BACKEND_LEARNING_GUIDE.md CP5,
    "refresh token JTI").
    """
    try:
        outstanding = OutstandingToken.objects.get(jti=jti)
    except OutstandingToken.DoesNotExist:
        return False
    BlacklistedToken.objects.get_or_create(token=outstanding)
    return True


def deactivate_session_by_jti(jti):
    """Mark the session tracking `jti` inactive (does not blacklist — callers
    that also need the token blacklisted, e.g. logout, call
    blacklist_by_jti() separately/first).
    """
    if not jti:
        return
    UserSession.objects.filter(refresh_token_jti=jti).update(is_active=False)


def revoke_session(session):
    """Fully revoke a single UserSession: blacklist its refresh token AND
    mark it inactive. Used by DELETE /api/v1/auth/sessions/<id>/.

    Never deletes the row — a revoked session stays visible in the user's
    own session history rather than silently disappearing.
    """
    blacklist_by_jti(session.refresh_token_jti)
    if session.is_active:
        session.is_active = False
        session.save(update_fields=["is_active"])


def revoke_all_sessions_except(user, keep_jti):
    """Revoke every active session belonging to `user` except the one whose
    JTI is `keep_jti` (the session making the current request, if any). Used
    by POST /api/v1/auth/logout-all/. Returns the number of sessions revoked.
    """
    queryset = UserSession.objects.filter(user=user, is_active=True)
    if keep_jti:
        queryset = queryset.exclude(refresh_token_jti=keep_jti)

    jtis = list(queryset.values_list("refresh_token_jti", flat=True))
    for jti in jtis:
        blacklist_by_jti(jti)
    if jtis:
        UserSession.objects.filter(refresh_token_jti__in=jtis).update(is_active=False)
    return len(jtis)
