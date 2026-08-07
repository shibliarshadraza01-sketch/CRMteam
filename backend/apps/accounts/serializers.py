"""CP3/CP4: request/response serialization for authentication.

Kept deliberately narrow — each serializer has one job:

- ``UserSerializer``       — the safe, public shape of a User (used in the
                             login response, /me, and the CP4 verify response).
- ``LoginSerializer``      — validates an email/password request body and,
                             on success, resolves it to an authenticated
                             ``User`` via Django's own auth backend.
- ``LogoutSerializer``     — validates a refresh token and blacklists it.
- ``LoginSuccessSerializer`` / ``SuperAdminChallengeSerializer`` — CP4,
                             output-only shapes documenting LoginView's two
                             possible response bodies for drf-spectacular
                             (see views.py's ``@extend_schema`` usage).
- ``SuperAdminVerifySerializer`` — CP4, validates a challenge token + access
                             code and resolves the SUPER_ADMIN it identifies.

No password, password hash, or access code is ever exposed through
``UserSerializer``. Token issuance itself lives in the views (see
apps/accounts/views.py) — these serializers validate input and, where
authentication is the validation (login, Super Admin verify), resolve
identity; they don't build HTTP responses themselves.
"""
from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .challenge import read_super_admin_challenge
from .models import UserSession
from .services import deactivate_session_by_jti

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """The only User shape ever sent to a client.

    Deliberately excludes password, is_staff, is_superuser, and every other
    field not needed by the frontend — see BACKEND_LEARNING_GUIDE.md CP3,
    "safe user information", for why this allowlist approach (rather than
    `exclude = [...]`) is the safer default.
    """

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role"]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """Validates an email/password login request.

    Authentication happens here, in ``validate()``, rather than in the view:
    DRF serializers are exactly where request-level business validation is
    expected to live, and doing it here means the view stays a thin
    orchestrator (validate -> issue tokens -> respond).
    """

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        request = self.context.get("request")
        # USERNAME_FIELD is "email" (see apps/accounts/models.py), so Django's
        # ModelBackend resolves this correctly even though the keyword here
        # is literally "email", not "username" — see BACKEND_LEARNING_GUIDE.md
        # CP3 for why that keyword has to match USERNAME_FIELD.
        user = authenticate(request=request, email=attrs["email"], password=attrs["password"])

        if user is None:
            # Deliberately identical whether the email doesn't exist, the
            # password is wrong, or the account is inactive (ModelBackend's
            # user_can_authenticate() already excludes is_active=False users
            # from authenticate()'s success path) — never reveal which.
            raise AuthenticationFailed("Invalid email or password.")

        attrs["user"] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Validates and blacklists a refresh token.

    CP5: also marks the matching UserSession inactive, keeping the session
    list in sync with the blacklist rather than leaving a phantom "active"
    row for a token that can no longer be used.
    """

    refresh = serializers.CharField(write_only=True)

    def validate_refresh(self, value):
        try:
            token = RefreshToken(value)
        except TokenError as exc:
            # Covers malformed tokens, expired tokens, and tokens that are
            # already blacklisted (SimpleJWT raises TokenError for all three
            # once the blacklist app is installed) — all surfaced as 400s via
            # normal DRF field-validation handling, not a raw 500.
            raise serializers.ValidationError(str(exc)) from exc

        self._token = token
        return value

    def save(self, **kwargs):
        self._token.blacklist()
        deactivate_session_by_jti(self._token.payload.get("jti"))


# --------------------------------------------------------------------------
# CP4: Super Admin secondary authentication
# --------------------------------------------------------------------------


class LoginSuccessSerializer(serializers.Serializer):
    """Output-only: LoginView's response shape for EMPLOYEE/MANAGER (and the
    shared shape SuperAdminVerifyView returns on success). Exists purely so
    drf-spectacular can document it — never instantiated for validation.
    """

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class SuperAdminChallengeSerializer(serializers.Serializer):
    """Output-only: LoginView's response shape for a SUPER_ADMIN whose primary
    credentials were valid but who still needs secondary verification. See
    views.py for why this and LoginSuccessSerializer are both attached to
    LoginView via @extend_schema rather than as its `serializer_class`.
    """

    secondary_verification_required = serializers.BooleanField(default=True)
    challenge = serializers.CharField(help_text="Short-lived signed token for POST /api/v1/auth/super-admin/verify/")


class SuperAdminVerifySerializer(serializers.Serializer):
    """Validates a Super Admin secondary-verification request.

    Resolves and attaches the identified ``User`` to ``validated_data["user"]``
    on success — mirroring LoginSerializer's pattern (§10/§11 of
    BACKEND_LEARNING_GUIDE.md CP3) so the view stays a thin
    validate-then-issue-tokens orchestrator.

    Every failure path (bad/expired/malformed challenge, unknown/inactive
    user, role no longer SUPER_ADMIN) raises the SAME "Invalid or expired
    challenge." error — deliberately not distinguished, for the same
    account-existence-privacy reason CP3's LoginSerializer unifies wrong-
    password and unknown-email. A wrong access code against an otherwise
    valid challenge is reported separately ("Invalid access code.") since,
    at that point, the challenge itself has already proven the caller
    completed primary authentication for a real, currently-active
    SUPER_ADMIN — there is no account-existence signal left to protect.
    """

    challenge = serializers.CharField(write_only=True)
    access_code = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        try:
            payload = read_super_admin_challenge(attrs["challenge"])
        except (signing.BadSignature, signing.SignatureExpired) as exc:
            raise AuthenticationFailed("Invalid or expired challenge.") from exc

        try:
            user = User.objects.get(pk=payload.get("user_id"))
        except (User.DoesNotExist, TypeError, ValueError) as exc:
            raise AuthenticationFailed("Invalid or expired challenge.") from exc

        # Re-check activity/role at verify time, not just at login time — a
        # challenge issued minutes ago must not still be honored if the
        # account was deactivated or demoted in the meantime (STEP 8:
        # "challenge belonging to inactive user" / "role changed after
        # challenge").
        if not user.is_active or user.role != User.Role.SUPER_ADMIN:
            raise AuthenticationFailed("Invalid or expired challenge.")

        # check_access_code() itself already returns False (never raises) for
        # a not-configured code, so "Super Admin without configured access
        # code" and "wrong access code" are indistinguishable to the caller
        # by construction — nothing extra needed here for that case.
        if not user.check_access_code(attrs["access_code"]):
            raise AuthenticationFailed("Invalid access code.")

        attrs["user"] = user
        return attrs


# --------------------------------------------------------------------------
# CP5: device sessions
# --------------------------------------------------------------------------


class UserSessionSerializer(serializers.ModelSerializer):
    """The only UserSession shape ever sent to a client.

    An explicit allowlist (same reasoning as UserSerializer, CP3 §11):
    `refresh_token_jti`, `user`, and `user_agent` are deliberately absent —
    the JTI in particular is the one piece of token-linked material this
    model exists to protect (see BACKEND_LEARNING_GUIDE.md CP5, "never
    expose the JTI"). `ip_address` is likewise absent — this project has no
    established policy requiring it be shown to the end user, so it stays
    out by the same "don't expose more than asked for" default CP3/CP4 set.
    """

    current_session = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = [
            "id",
            "device_name",
            "device_type",
            "browser",
            "operating_system",
            "created_at",
            "last_used_at",
            "current_session",
        ]
        read_only_fields = fields

    def get_current_session(self, obj) -> bool:
        """True if `obj` is the session behind the access token making this
        request — see views.py's `_issue_token_pair_response()`, which embeds
        the refresh token's JTI as a custom `session_jti` claim on the access
        token specifically so this comparison is possible without ever
        storing or transmitting the refresh token itself.
        """
        current_jti = self.context.get("current_session_jti")
        return bool(current_jti) and obj.refresh_token_jti == current_jti


class RevokeAllResponseSerializer(serializers.Serializer):
    """Output-only: POST /api/v1/auth/logout-all/'s response shape, for drf-spectacular."""

    revoked = serializers.IntegerField(help_text="Number of sessions revoked (excludes the current session).")
