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
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .challenge import issue_super_admin_challenge
from .models import UserSession
from .serializers import (
    LoginSerializer,
    LoginSuccessSerializer,
    LogoutSerializer,
    RevokeAllResponseSerializer,
    SuperAdminChallengeSerializer,
    SuperAdminVerifySerializer,
    UserSerializer,
    UserSessionSerializer,
)
from .services import (
    create_session,
    revoke_all_sessions_except,
    revoke_session,
    touch_session_on_refresh,
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
    refresh.access_token[SESSION_JTI_CLAIM] = refresh["jti"]
    create_session(user=user, refresh_token=refresh, request=request)

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        },
        status=status.HTTP_200_OK,
    )


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
class LoginView(generics.GenericAPIView):
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


class LogoutView(generics.GenericAPIView):
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
class SuperAdminVerifyView(generics.GenericAPIView):
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

    def post(self, request, *args, **kwargs):
        old_jti = self._jti_from_token_string(request.data.get("refresh"))

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200 and old_jti:
            new_refresh_str = response.data.get("refresh")
            new_jti = self._jti_from_token_string(new_refresh_str) if new_refresh_str else None
            touch_session_on_refresh(old_jti=old_jti, new_jti=new_jti)

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
