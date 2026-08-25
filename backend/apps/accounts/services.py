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
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from .models import UserSession
from .session_utils import build_device_name, get_client_ip, parse_user_agent

User = get_user_model()


def get_manager_for_user(user):
    """The ``User`` who manages ``user``, or ``None``.

    Resolved from the EXISTING ``apps.organization`` Team/Membership
    hierarchy — the same structure ``apps.crm.services.managed_user_ids()``
    already uses to decide what a Manager can see. Deliberately NOT a new
    ``User.manager`` FK: a second, parallel definition of "who manages
    whom" could disagree with the one RBAC scoping actually enforces,
    which is precisely the "Employee referencing a nonexistent Manager /
    inconsistent relationships" class of bug worth avoiding.
    """
    from apps.organization.models import Membership

    membership = (
        Membership.objects.filter(user=user, team__manager__isnull=False)
        .select_related("team__manager")
        .order_by("-joined_at")
        .first()
    )
    return membership.team.manager if membership is not None else None


def get_employees_for_manager(manager):
    """The reverse direction of ``get_manager_for_user()`` — every user who
    is a member of a team ``manager`` leads (excluding the manager
    themselves). Both directions read the same Team/Membership rows, so
    they can never disagree.
    """
    from apps.organization.models import Membership, Team

    team_ids = Team.objects.filter(manager=manager).values_list("id", flat=True)
    return (
        User.objects.filter(team_memberships__team_id__in=team_ids)
        .exclude(pk=manager.pk)
        .distinct()
        .order_by("email")
    )


def _default_team_for_manager(manager):
    """The team a newly-assigned employee joins under ``manager``.

    Uses an existing team the manager already leads when there is one.
    Otherwise creates one, auto-creating the Organization/Department above
    it if the deployment has none yet — the same "a real default beats an
    error" reasoning ``apps.attendance.services.get_active_shift_configuration()``
    already applies. Assigning a manager must not fail because nobody has
    opened the org-structure screen yet.
    """
    from apps.organization.models import Department, Organization, Team

    existing = Team.objects.filter(manager=manager).order_by("id").first()
    if existing is not None:
        return existing

    organization = Organization.objects.order_by("id").first()
    if organization is None:
        organization = Organization.objects.create(name="Default Organization", slug="default-organization")

    department = Department.objects.filter(organization=organization).order_by("id").first()
    if department is None:
        department = Department.objects.create(organization=organization, name="General")

    manager_label = manager.full_name or manager.email
    return Team.objects.create(
        department=department,
        name=f"{manager_label}'s Team"[:200],
        manager=manager,
    )


@transaction.atomic
def assign_user_to_manager(user, manager):
    """Make ``manager`` the manager of ``user``, or clear the assignment
    when ``manager`` is ``None``.

    Writes to ``apps.organization.Membership`` — the one mechanism this
    project already scopes RBAC by — so the relationship is genuinely
    persisted and immediately effective for lead/customer visibility, not
    merely displayed.

    Returns ``manager``.

    ATOMICITY (Phase 4 transaction-safety audit). The "drop the old
    assignment, then create the new one" pair below must not be separable.
    Un-transacted, a failure after the ``delete()`` but before the
    ``update_or_create()`` — a constraint, a database error, an exception
    raised while auto-creating the team/department/organization in
    ``_default_team_for_manager()`` — left the employee with NO manager at
    all: not the old one, not the requested one. That is worse than the
    operation simply failing, and it silently NARROWS what the previous
    manager can see (``managed_user_ids()`` reads these very rows), so
    leads and customers quietly drop out of that manager's lists with
    nothing recording why.
    """
    from apps.organization.models import Membership, Team

    # Drop any existing manager assignment first, so a user is never
    # simultaneously on two different managers' teams (which would make
    # "who is this employee's manager?" ambiguous, and would widen what
    # the OTHER manager can see).
    managed_team_ids = Team.objects.filter(manager__isnull=False).values_list("id", flat=True)
    Membership.objects.filter(user=user, team_id__in=managed_team_ids).delete()

    if manager is None:
        return None

    team = _default_team_for_manager(manager)
    Membership.objects.update_or_create(
        user=user, team=team, defaults={"role": Membership.Role.MEMBER}
    )
    return manager


@transaction.atomic
def create_managed_user(
    email,
    password,
    *,
    role,
    first_name="",
    last_name="",
    username=None,
    phone="",
    date_joined=None,
    is_active=True,
    manager=None,
):
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

    Staff-management pass: also accepts the profile-only fields the Super
    Admin's staff-creation form collects (``username`` — a DISPLAY handle,
    never an authentication credential, see ``apps/accounts/models.py`` —
    plus ``phone``, ``date_joined``, ``is_active``). ``date_joined``
    defaults to the model's own ``timezone.now`` when not supplied, so an
    omitted joining date behaves exactly as before.

    ``manager``, when given, assigns the new user to that manager's team
    via ``assign_user_to_manager()`` — i.e. through the real
    ``apps.organization`` Membership hierarchy that RBAC scoping already
    reads, not a display-only field.

    (The former free-text ``department`` argument was removed along with
    ``User.department``: it was a label nothing in the application ever
    read or scoped by. The organizational hierarchy's own
    ``apps.organization.Department`` model is a different, still-current
    concept and is untouched.)

    ATOMICITY (Phase 4 transaction-safety audit). Creating a user is two
    writes when a ``manager`` is supplied: the ``User`` row, then the
    ``apps.organization`` Membership (and, on a manager's first-ever
    assignment, the Team/Department/Organization above it). Un-transacted,
    a failure in the second step left a fully-created, LOGIN-CAPABLE
    account with no reporting line — invisible to the manager the Super
    Admin just assigned them to, while the API reported the create as
    failed. The admin's natural response, retrying the form, then hit
    "user with this email already exists" for an account they were told
    was never created. Either the whole user exists with their manager, or
    nothing does.
    """
    extra = {}
    if date_joined is not None:
        extra["date_joined"] = date_joined
    user = User.objects.create_user(
        email=email,
        password=password,
        role=role,
        first_name=first_name,
        last_name=last_name,
        username=username or None,
        phone=phone,
        is_active=is_active,
        **extra,
    )
    if manager is not None:
        assign_user_to_manager(user, manager)
    return user


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


def apply_security_settings(
    user, *, username=None, new_password=None, new_access_code=None, change_username=False
):
    """Write the security-sensitive settings a user changed on themselves.

    Called ONLY after ``apps.accounts.verification.verify_security_change()``
    has already approved the change (see ``views.SecuritySettingsView``) —
    this function performs no verification of its own on purpose, so
    "was this verified?" has exactly one answer in exactly one place.

    Returns the list of field names actually changed. Never returns or logs
    any secret value.
    """
    updated = []
    fields = []

    if change_username:
        user.username = username or None
        updated.append("username")
        fields.append("username")

    if new_password:
        user.set_password(new_password)
        updated.append("password")
        fields.append("password")

    if new_access_code:
        user.set_access_code(new_access_code)
        updated.append("access_code")
        fields.append("super_admin_access_code_hash")

    if fields:
        # save() enforces the model's own invariants (email lowercasing,
        # blank-username -> NULL, access-code clearing for non-Super-Admins),
        # so a full save is deliberate here rather than update_fields alone.
        user.save()
    return updated


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
