"""CP3: request/response serialization for authentication.

Kept deliberately narrow — three serializers, each with one job:

- ``UserSerializer``       — the safe, public shape of a User (used in the
                             login response and by /me).
- ``LoginSerializer``      — validates an email/password request body and,
                             on success, resolves it to an authenticated
                             ``User`` via Django's own auth backend.
- ``LogoutSerializer``     — validates a refresh token and blacklists it.

No password, password hash, or token value is ever exposed through
``UserSerializer``. Token issuance itself lives in the views (see
apps/accounts/views.py) — these serializers validate input and, where
authentication is the validation (login), resolve identity; they don't build
HTTP responses themselves.
"""
from django.contrib.auth import authenticate, get_user_model
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

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
    """Validates and blacklists a refresh token."""

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
