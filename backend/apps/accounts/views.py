"""CP3/CP4/CP5: authentication + device session API views.

Eight endpoints, mounted at /api/v1/auth/ (see apps/accounts/urls.py):

- POST /login/               -> LoginView (public). For EMPLOYEE/MANAGER,
                                 behaves exactly as CP3: returns access +
                                 refresh + user (and now also creates a
                                 UserSession — CP5). For SUPER_ADMIN, does NOT
                                 issue tokens — returns a short-lived
                                 challenge instead (CP4).
- POST /super-admin/verify/  -> SuperAdminVerifyView (public; CP4). Exchanges
                                 a valid challenge + access code for the
                                 normal access + refresh pair (and creates a
                                 UserSession — CP5).
- POST /refresh/  -> SessionAwareTokenRefreshView (CP5). A thin wrapper
                      around SimpleJWT's own TokenRefreshView that additionally
                      updates the matching session's last_used_at (and its
                      tracked JTI, if rotation issued a new one).
- POST /logout/   -> LogoutView  (public; the refresh token itself is the
                      credential being acted on). Now also deactivates the
                      matching UserSession (CP5).
- GET  /me/       -> MeView      (requires a valid access token)
- GET  /sessions/           -> SessionListView   (CP5, requires access token)
- DELETE /sessions/<id>/    -> SessionRevokeView  (CP5, requires access token)
- POST /logout-all/         -> LogoutAllView      (CP5, requires access token)

Views stay thin: validate via a serializer, issue/blacklist tokens via
SimpleJWT, read/write UserSession via apps/accounts/services.py, return a
response. No authentication logic is duplicated here — password/access-code
checking lives in Django's auth backend and apps/accounts/models.py's
check_access_code(); token signing/verification lives in SimpleJWT; challenge
signing/verification lives in apps/accounts/challenge.py; session persistence
lives in apps/accounts/services.py.
"""
from django.contrib.auth import get_user_model
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .challenge import issue_super_admin_challenge
from .models import UserSession
from .permissions import ReadOnlyOrSuperAdmin
from .profiles import build_staff_profile, can_view_staff_profile
from .serializers import (
    LoginSerializer,
    LoginSuccessSerializer,
    LogoutSerializer,
    RevokeAllResponseSerializer,
    SecuritySettingsResponseSerializer,
    SecuritySettingsSerializer,
    SecurityVerificationMethodSerializer,
    StaffProfileSerializer,
    SuperAdminChallengeSerializer,
    SuperAdminVerifySerializer,
    UserCreateSerializer,
    UserManagementSerializer,
    UserSerializer,
    UserSessionSerializer,
)
from .services import (
    activate_user,
    apply_security_settings,
    create_managed_user,
    create_session,
    deactivate_user,
    revoke_all_sessions_except,
    revoke_session,
    touch_session_on_refresh,
)
from .verification import (
    CHANGE_ACCESS_CODE,
    CHANGE_PASSWORD,
    CHANGE_USERNAME,
    describe_security_verification,
    verify_security_change,
)

User = get_user_model()

# The claim name used to link an access token back to the UserSession its
# sibling refresh token created. See _issue_token_pair_response() and
# _current_session_jti() below, and BACKEND_LEARNING_GUIDE.md CP5, "how a
# request knows which session it is".
SESSION_JTI_CLAIM = "session_jti"


def _issue_token_pair_response(user, request):
    """Shared by LoginView (non-Super-Admin) and SuperAdminVerifyView.

    The only place RefreshToken.for_user() is called — one code path issuing
    the CP3 SimpleJWT pair, regardless of which authentication path reached
    it. CP4 does NOT implement a separate/permanent Super Admin token type:
    a verified Super Admin's tokens are ordinary SimpleJWT tokens that
    participate in the same refresh/blacklist lifecycle as anyone else's.

    CP5 additions: the access token gets a custom `session_jti` claim (the
    refresh token's own jti) so a later authenticated request can identify
    "this is the session that request came from"; and a UserSession row is
    created to track the new refresh token.
    """
    refresh = RefreshToken.for_user(user)
    # ``refresh.access_token`` is a @property — every access mints a BRAND
    # NEW AccessToken instance (see SimpleJWT's tokens.py), never a cached
    # one. Setting the claim via `refresh.access_token[...] = ...` was
    # mutating a throwaway instance that the very next `.access_token`
    # access (below) would discard, so the token actually returned to the
    # client never carried this claim — silently breaking
    # `_current_session_jti()` for every login. Setting it on the REFRESH
    # token's own payload instead means every AccessToken minted from it
    # (here, and after every future rotation — see
    # SessionAwareTokenRefreshView below) inherits it via the property's
    # claim-copy loop, since "session_jti" isn't in SimpleJWT's
    # `no_copy_claims`.
    refresh[SESSION_JTI_CLAIM] = refresh["jti"]
    access_token = refresh.access_token
    create_session(user=user, refresh_token=refresh, request=request)

    return Response(
        {
            "access": str(access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        },
        status=status.HTTP_200_OK,
    )


class _CredentialsInBodyAuthHeaderMixin:
    """For views that set ``authentication_classes = []`` (the credential
    being validated lives in the request BODY — password, refresh token,
    challenge — not in an ``Authorization`` header, and a client's stale
    Bearer token must never block the request from reaching that body
    validation at all).

    That emptiness has a surprising side effect: DRF's exception handler
    only returns 401 for an ``AuthenticationFailed`` if
    ``get_authenticate_header()`` finds a non-empty ``WWW-Authenticate``
    value to attach (``rest_framework/views.py``'s
    ``exception_handler()``) — with no authenticators registered, it
    silently coerces the response to 403 instead. Every one of these
    views' serializers legitimately raises ``AuthenticationFailed`` for
    wrong credentials (wrong password, invalid/expired challenge, wrong
    access code) and expects a real 401, per CP3/CP4's own tests. This
    mixin restores a normal ``WWW-Authenticate`` value without
    reintroducing actual token authentication on these endpoints.
    """

    def get_authenticate_header(self, request):
        return "Bearer"


def _current_session_jti(request):
    """Extract the session_jti claim from the validated access token behind
    this request, or None if unavailable (e.g. an older token issued before
    CP5, which simply has no such claim).
    """
    auth = getattr(request, "auth", None)
    if auth is None:
        return None
    return auth.get(SESSION_JTI_CLAIM)


@extend_schema(
    responses=PolymorphicProxySerializer(
        component_name="LoginResponse",
        serializers=[LoginSuccessSerializer, SuperAdminChallengeSerializer],
        resource_type_field_name=None,
    )
)
class LoginView(_CredentialsInBodyAuthHeaderMixin, generics.GenericAPIView):
    """POST /api/v1/auth/login/ — email + password -> two possible outcomes.

    EMPLOYEE / MANAGER: access + refresh + user (unchanged from CP3), and a
    UserSession is created (CP5).

    SUPER_ADMIN: primary credentials alone are NOT sufficient (CP4). The
    response instead carries `secondary_verification_required: true` and a
    short-lived `challenge` to be presented, together with the secondary
    access code, to POST /api/v1/auth/super-admin/verify/. No session is
    created at this stage — only a successful /super-admin/verify/ call
    issues tokens and therefore a session.
    """

    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # logging in does not require being already authenticated
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        if user.role == User.Role.SUPER_ADMIN:
            challenge = issue_super_admin_challenge(user)
            return Response(
                {"secondary_verification_required": True, "challenge": challenge},
                status=status.HTTP_200_OK,
            )

        return _issue_token_pair_response(user, request)


class MeView(generics.RetrieveAPIView):
    """GET /api/v1/auth/me/ — the authenticated user's safe identity info.

    Requires a valid, non-expired access token. This is the endpoint the
    frontend will call on app load to restore "who is logged in" from a
    stored token, without ever needing the password again.
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class LogoutView(_CredentialsInBodyAuthHeaderMixin, generics.GenericAPIView):
    """POST /api/v1/auth/logout/ — blacklist a refresh token.

    Takes the refresh token (not the access token) in the body. Blacklisting
    it means it can never again be exchanged for a new access token via
    /refresh/, even though it hasn't reached its natural REFRESH_TOKEN_LIFETIME
    expiry yet. This is SimpleJWT's supported logout pattern; no custom
    server-side session table replaces it — UserSession (CP5) only tracks
    metadata alongside it. LogoutSerializer.save() also deactivates the
    matching UserSession.
    """

    serializer_class = LogoutSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # possessing a valid refresh token is the credential here

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)


@extend_schema(responses={200: LoginSuccessSerializer})
class SuperAdminVerifyView(_CredentialsInBodyAuthHeaderMixin, generics.GenericAPIView):
    """POST /api/v1/auth/super-admin/verify/ — CP4 secondary verification.

    Exchanges a valid (unexpired, correctly-signed) challenge token plus the
    matching secondary access code for the normal SimpleJWT access + refresh
    pair, and creates a UserSession (CP5) exactly like an ordinary login
    does. This is the ONLY place a SUPER_ADMIN actually becomes authenticated
    — the challenge itself (see /login/) is not an authenticated session and
    cannot be used against any other endpoint.

    Rate-limited (CP4 STEP 9): see `throttle_scope` below and
    BACKEND_LEARNING_GUIDE.md CP4, "brute-force considerations", for why this
    is a real but explicitly non-production-grade speed bump, not a
    distributed rate limiter.
    """

    serializer_class = SuperAdminVerifySerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # the challenge + access code are the credential here
    throttle_scope = "super_admin_verify"
    throttle_classes = [ScopedRateThrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        return _issue_token_pair_response(user, request)


class SessionAwareTokenRefreshView(TokenRefreshView):
    """POST /api/v1/auth/refresh/ — CP5 wrapper around SimpleJWT's own view.

    Delegates 100% of the actual refresh logic (validating the incoming
    refresh token, honoring rotation/blacklist settings, rejecting invalid/
    expired/blacklisted tokens) to `TokenRefreshView.post()` — see CP3's
    reasoning for why that logic is not reimplemented. The only addition:
    after a successful (200) refresh, the matching UserSession's
    `last_used_at` is advanced, and — because rotation is enabled — its
    tracked JTI is updated to the newly-issued refresh token's JTI so a
    later revoke/logout-all still finds the right row.

    A failed refresh (any non-200 response) does not touch UserSession at
    all — there is nothing to update, and SimpleJWT has already rejected the
    request for its own reasons.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token_refresh"

    def post(self, request, *args, **kwargs):
        old_jti = self._jti_from_token_string(request.data.get("refresh"))

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200 and old_jti:
            new_refresh_str = response.data.get("refresh")
            new_jti = self._jti_from_token_string(new_refresh_str) if new_refresh_str else None
            touch_session_on_refresh(old_jti=old_jti, new_jti=new_jti)

            # Rotation is enabled, so `new_jti` (the new refresh token's own
            # jti) is what UserSession.refresh_token_jti now holds (see
            # touch_session_on_refresh() above). The access token SimpleJWT
            # just minted still carries whatever `session_jti` claim was on
            # the OLD refresh token's payload (STALE — the jti from before
            # this rotation), since ROTATE_REFRESH_TOKENS reuses the same
            # RefreshToken object and only mutates its jti in place. Without
            # re-stamping it here, `_current_session_jti()` would stop
            # matching this session after the very first refresh.
            if new_jti and response.data.get("access"):
                access = AccessToken(response.data["access"])
                access[SESSION_JTI_CLAIM] = new_jti
                response.data["access"] = str(access)

        return response

    @staticmethod
    def _jti_from_token_string(token_string):
        if not token_string:
            return None
        try:
            return RefreshToken(token_string).payload.get("jti")
        except TokenError:
            return None


class SessionListView(generics.ListAPIView):
    """GET /api/v1/auth/sessions/ — the caller's own active sessions.

    Always scoped to `request.user` — there is no way to request another
    user's sessions through this endpoint, for any role, Super Admin
    included (CP5 STEP: "No admin shortcuts").
    """

    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            # drf-spectacular introspects this view without a real
            # authenticated request; filtering by self.request.user would
            # crash against an AnonymousUser. An empty queryset is enough
            # for schema generation to resolve the response model.
            return UserSession.objects.none()
        return UserSession.objects.filter(user=self.request.user, is_active=True)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["current_session_jti"] = _current_session_jti(self.request)
        return context


class SessionRevokeView(generics.DestroyAPIView):
    """DELETE /api/v1/auth/sessions/<id>/ — revoke exactly one session.

    `get_queryset()` is scoped to `request.user`, so a session ID belonging
    to a different user is simply not found (404) rather than a distinguishable
    403 — this endpoint never confirms or denies that a given ID exists for
    someone else (CP5 STEP: "cross-user access denied").

    "Revoke" blacklists the underlying refresh token and marks the row
    inactive; it does not delete the row (see services.revoke_session()).
    """

    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        revoke_session(instance)


@extend_schema(request=None, responses={200: RevokeAllResponseSerializer})
class LogoutAllView(APIView):
    """POST /api/v1/auth/logout-all/ — revoke every OTHER active session.

    Deliberately preserves the session the request itself is authenticated
    with (identified via the access token's session_jti claim — see
    _current_session_jti()) so calling this endpoint does not immediately
    log the caller out of the device they're using right now.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        revoked = revoke_all_sessions_except(request.user, _current_session_jti(request))
        return Response({"revoked": revoked}, status=status.HTTP_200_OK)


class UserListCreateView(generics.ListCreateAPIView):
    """Final-completion-pass: the admin-facing Users management API.

    Read (list): any authenticated user — matches the same "org chart is
    visible to everyone" rule ``apps.organization``'s Department/Team
    endpoints already use. Write (create): Super Admin only — creating an
    account is not a Manager-level decision, the same rule
    ``apps.organization``'s ``OrganizationWritePermission`` applies to
    creating an Organization itself.
    """

    queryset = User.objects.all().order_by("email")
    permission_classes = [permissions.IsAuthenticated, ReadOnlyOrSuperAdmin]
    filterset_fields = ["role", "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    ordering_fields = ["email", "date_joined", "role"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserManagementSerializer

    def perform_create(self, serializer):
        data = serializer.validated_data
        user = create_managed_user(
            data["email"],
            data["password"],
            role=data.get("role", User.Role.EMPLOYEE),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            username=data.get("username"),
            phone=data.get("phone", ""),
            department=data.get("department", ""),
            date_joined=data.get("date_joined"),
            is_active=data.get("is_active", True),
        )
        serializer.instance = user


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """``DELETE`` here is deliberately NON-DESTRUCTIVE.

    A `User` row is referenced (via ``SET_NULL`` FKs) by leads, customers,
    invoices, attendance sessions, communication logs, audit entries and
    every ``created_by``/``updated_by`` column in the system. Really
    deleting the row would silently null out that entire historical
    attribution — exactly what the spec's "preserve historical records"
    rule forbids. So the Users management API has NO hard delete at all:
    ``DELETE /users/<id>/`` performs the same reversible deactivation as
    ``POST /users/<id>/deactivate/`` and returns ``200`` with the updated
    user (not ``204``), so a caller can see the account is now inactive
    rather than gone.
    """

    queryset = User.objects.all()
    serializer_class = UserManagementSerializer
    permission_classes = [permissions.IsAuthenticated, ReadOnlyOrSuperAdmin]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    @extend_schema(responses={200: UserManagementSerializer})
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        deactivate_user(user)
        return Response(
            {
                "detail": (
                    "Account deactivated. User records are never hard-deleted — all "
                    "historical CRM data owned by or attributed to this user is preserved."
                ),
                "user": self.get_serializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(request=None, responses={200: UserManagementSerializer})
class UserActivateView(generics.GenericAPIView):
    queryset = User.objects.all()
    serializer_class = UserManagementSerializer
    permission_classes = [permissions.IsAuthenticated, ReadOnlyOrSuperAdmin]

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        activate_user(user)
        return Response(self.get_serializer(user).data)


@extend_schema(request=None, responses={200: UserManagementSerializer})
class UserDeactivateView(generics.GenericAPIView):
    queryset = User.objects.all()
    serializer_class = UserManagementSerializer
    permission_classes = [permissions.IsAuthenticated, ReadOnlyOrSuperAdmin]

    def post(self, request, *args, **kwargs):
        user = self.get_object()
        deactivate_user(user)
        return Response(self.get_serializer(user).data)


@extend_schema(responses={200: StaffProfileSerializer})
class StaffProfileView(APIView):
    """``GET /api/v1/auth/users/<id>/profile/`` — the consolidated staff
    profile (see ``apps/accounts/profiles.py``).

    Scoping (``profiles.can_view_staff_profile()``): Super Admin -> anyone;
    Manager -> themselves + their own ``managed_user_ids()``; Employee ->
    themselves only. A target outside the caller's reach returns 404, never
    403 — the same "never confirm a record exists for someone else" rule
    the rest of this project already uses.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        target = User.objects.filter(pk=pk).first()
        if target is None or not can_view_staff_profile(request.user, target):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(build_staff_profile(target), status=status.HTTP_200_OK)


class SecuritySettingsView(generics.GenericAPIView):
    """``GET``/``POST /api/v1/auth/settings/security/`` — the caller's OWN
    security-sensitive settings (username, password, Super Admin access
    code).

    ``GET`` describes the verification step the configured provider
    requires, so a frontend can render it before submitting.

    ``POST`` runs ``verification.verify_security_change()`` FIRST and
    aborts with 403 if it does not pass — nothing is written unless every
    requested change verified. Applies only to ``request.user``: this
    endpoint can never change another account's credentials (staff
    accounts are managed through the Users API, which sets an initial
    password at creation time only).

    The access code is Super-Admin-only by construction (the model clears
    the hash for any other role on save — see ``User.save()``), so
    requesting one as a Manager/Employee is rejected explicitly rather
    than silently ignored.
    """

    serializer_class = SecuritySettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "super_admin_verify"

    @extend_schema(responses={200: SecurityVerificationMethodSerializer})
    def get(self, request, *args, **kwargs):
        return Response(describe_security_verification(), status=status.HTTP_200_OK)

    @extend_schema(request=SecuritySettingsSerializer, responses={200: SecuritySettingsResponseSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user

        if "new_access_code" in data and user.role != User.Role.SUPER_ADMIN:
            return Response(
                {"detail": "Only a Super Admin has a secondary access code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify BEFORE writing anything — one verification covers the whole
        # atomic change set (see apps/accounts/verification.py).
        for change_type, key in (
            (CHANGE_USERNAME, "username"),
            (CHANGE_PASSWORD, "new_password"),
            (CHANGE_ACCESS_CODE, "new_access_code"),
        ):
            if key in data:
                verify_security_change(user, change_type, request.data)

        updated_fields = apply_security_settings(
            user,
            username=data["username"] if "username" in data else None,
            new_password=data.get("new_password"),
            new_access_code=data.get("new_access_code"),
            change_username=("username" in data),
        )
        return Response(
            {"updated_fields": updated_fields, "user": UserManagementSerializer(user).data},
            status=status.HTTP_200_OK,
        )
