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
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .challenge import read_super_admin_challenge
from .models import UserSession
from .services import assign_user_to_manager, deactivate_session_by_jti, get_manager_for_user

User = get_user_model()


#: Roles that may stand at the top of a reporting line.
MANAGERIAL_ROLES = (User.Role.MANAGER, User.Role.SUPER_ADMIN)


def selectable_managers():
    """The users a Super Admin may legitimately pick as someone's manager.

    ONE definition, read by the API's own choice metadata
    (``ManagerAssignmentField.get_choices()``) and mirrored by the
    frontend's picker — so the list a user is shown and the list the
    server accepts cannot drift apart.

    Deactivated accounts are excluded on purpose: a deactivated manager
    cannot log in, so pointing a reporting line at one silently orphans
    the employee.
    """
    return User.objects.filter(is_active=True, role__in=MANAGERIAL_ROLES).order_by("email")


def validate_manager_assignment(manager, *, role, instance=None):
    """Every business rule about WHO may manage WHOM, in one place, each
    with its own actionable message.

    Shared by ``UserCreateSerializer`` and ``UserManagementSerializer`` so
    creating a user and editing one can never enforce different rules —
    the create path used to be the looser of the two simply by having
    fewer checks written out.

    ``role`` is the role the user will HAVE once this request is applied
    (which the same request may be changing). ``instance`` is the user
    being edited, or ``None`` on create.

    Raises ``serializers.ValidationError`` keyed on ``manager``; returns
    ``None`` when the assignment is allowed. ``manager=None`` (clear the
    assignment) is always allowed.
    """
    if manager is None:
        return

    if instance is not None and manager.pk == instance.pk:
        raise serializers.ValidationError({"manager": "A user cannot be their own manager."})
    if role != User.Role.EMPLOYEE:
        raise serializers.ValidationError(
            {"manager": "Only an Employee can be assigned to a manager."}
        )
    if manager.role not in MANAGERIAL_ROLES:
        raise serializers.ValidationError(
            {
                "manager": (
                    f"{manager.full_name or manager.email} is not a manager, so this "
                    "employee cannot report to them."
                )
            }
        )
    if not manager.is_active:
        raise serializers.ValidationError(
            {
                "manager": (
                    f"{manager.full_name or manager.email} is deactivated and cannot be "
                    "assigned as a manager. Reactivate that account first, or choose "
                    "another manager."
                )
            }
        )


class ManagerAssignmentField(serializers.PrimaryKeyRelatedField):
    """The "assign this employee to a Manager" field.

    Writable by primary key, nullable (``null`` clears the assignment).

    The queryset deliberately spans ALL users rather than only the
    assignable ones. Narrowing it here looks like stricter validation but
    is actually worse: ``PrimaryKeyRelatedField`` reports anything outside
    its queryset as ``Invalid pk "4" - object does not exist``, so
    picking a real-but-deactivated manager, picking a peer Employee, and
    picking yourself all produced that one identical, factually FALSE
    message about a user the admin can plainly see in the list — and the
    precise per-case checks in ``validate()`` below became unreachable
    dead code. Resolution stays honest here ("does not exist" means it
    really does not exist) and every business rule about WHO may be a
    manager is enforced in ``validate()``, each with its own actionable
    message.

    Which users are offered as choices is unchanged — see
    ``selectable_managers()``, which the browsable API / OPTIONS metadata
    and the frontend picker both read.

    Not a model field: reads resolve through
    ``services.get_manager_for_user()`` and writes through
    ``services.assign_user_to_manager()``, both of which use the existing
    ``apps.organization`` Team/Membership hierarchy that RBAC scoping
    already enforces. See those functions for why no parallel
    ``User.manager`` FK was introduced.
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_null", True)
        kwargs.setdefault("queryset", User.objects.none())
        super().__init__(**kwargs)

    def get_queryset(self):
        # Every user, so an unknown pk is the ONLY thing reported as
        # "does not exist". See the class docstring.
        return User.objects.all().order_by("email")

    def get_choices(self, cutoff=None):
        # Browsable-API / OPTIONS metadata still advertises only the users
        # who may actually be picked, matching the frontend's picker.
        queryset = selectable_managers()
        if cutoff is not None:
            queryset = queryset[:cutoff]
        return {
            str(self.to_representation(item)): self.display_value(item) for item in queryset
        }

    def get_attribute(self, instance):
        # Return the User instance itself; to_representation turns it into
        # a pk. Returning None here yields a null `manager` in the payload.
        return get_manager_for_user(instance)


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


class UserManagementSerializer(serializers.ModelSerializer):
    """Final-completion-pass: the Users management API's list/retrieve/
    update shape — a superset of ``UserSerializer`` (adds ``is_active``/
    ``date_joined``, both genuinely needed by an admin user list) used
    ONLY by ``UserViewSet`` (Manager/Super-Admin-only, see permissions.py),
    never by any client-facing "who am I" endpoint. Still deliberately
    excludes password/access-code fields — see ``UserSerializer``'s own
    docstring for why that boundary matters.
    """

    full_name = serializers.CharField(read_only=True)
    manager = ManagerAssignmentField()
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "username", "first_name", "last_name", "full_name",
            "phone", "manager", "manager_name", "role", "is_active", "date_joined",
        ]
        read_only_fields = ["id", "full_name", "manager_name"]
        extra_kwargs = {
            # A blank submission means "no username", stored as NULL — see
            # ``User.save()``. Without allow_null/required=False a PATCH that
            # simply omits it would be fine but an explicit "" would 400.
            "username": {"required": False, "allow_null": True, "allow_blank": True},
        }

    def validate_username(self, value):
        return value or None

    def get_manager_name(self, obj) -> str:
        # Return type annotated so drf-spectacular can resolve the schema
        # without falling back to a guess (apps/*/tests/test_openapi.py
        # asserts the generated schema produces NO warnings).
        manager = get_manager_for_user(obj)
        return (manager.full_name or manager.email) if manager is not None else ""

    def validate(self, attrs):
        # Same reporting-line invariant as UserCreateSerializer — literally
        # the same function — evaluated against the role this PATCH will
        # leave the user with (which may itself be changing in this same
        # request).
        validate_manager_assignment(
            attrs.get("manager"),
            role=attrs.get("role", self.instance.role if self.instance else User.Role.EMPLOYEE),
            instance=self.instance,
        )
        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        # `manager` is not a model field — it is persisted through the
        # apps.organization Membership hierarchy, so it must be popped
        # before ModelSerializer tries to setattr it onto the User.
        # `None` is a meaningful value here (clear the assignment), so
        # presence is tested with a sentinel rather than truthiness.
        #
        # Atomic (Phase 4 transaction-safety audit) because this is TWO
        # writes to two different tables: the User's own columns, then the
        # Membership row behind `manager`. A failure in the second half
        # previously left the profile edit applied (a changed role, email,
        # or is_active) with the reporting-line change silently dropped,
        # while the caller saw an error and assumed nothing was saved.
        # Role and manager are especially dangerous to split: `role` is
        # what `validate_manager_assignment()` checks the manager against,
        # so a half-applied edit can persist exactly the combination
        # validation exists to reject.
        sentinel = object()
        manager = validated_data.pop("manager", sentinel)
        user = super().update(instance, validated_data)
        if manager is not sentinel:
            assign_user_to_manager(user, manager)
        return user


class UserCreateSerializer(serializers.ModelSerializer):
    """Write-only ``password`` — create only, via
    ``services.create_managed_user()`` (see ``UserListCreateView.perform_create()``),
    which routes through ``User.objects.create_user()`` for hashing.

    Staff-management pass: carries the full "User/Staff Management"
    creation form — Full Name (``first_name``/``last_name``), Username
    (a PROFILE field only; authentication stays email+password),
    Email, Phone, Role, Manager, Joining date (``date_joined``),
    Status (``is_active``), Credentials (``password``).

    ``department`` was removed — see ``apps/accounts/models.py``.
    """

    password = serializers.CharField(write_only=True, trim_whitespace=False, min_length=8)
    manager = ManagerAssignmentField()

    class Meta:
        model = User
        fields = [
            "id", "email", "password", "username", "first_name", "last_name",
            "phone", "manager", "role", "date_joined", "is_active",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "username": {"required": False, "allow_null": True, "allow_blank": True},
            "date_joined": {"required": False},
            "is_active": {"required": False},
        }

    def validate_username(self, value):
        return value or None

    def validate(self, attrs):
        # A Manager or Super Admin does not report to a Manager through the
        # employee->team hierarchy; silently accepting one would create a
        # reporting line the rest of the app does not model. Shared with
        # UserManagementSerializer so create and edit enforce identically.
        validate_manager_assignment(
            attrs.get("manager"), role=attrs.get("role", User.Role.EMPLOYEE)
        )
        return attrs


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


# --------------------------------------------------------------------------
# Staff-management pass: security-sensitive settings
# --------------------------------------------------------------------------


class SecuritySettingsSerializer(serializers.Serializer):
    """Input for ``POST /api/v1/auth/settings/security/``.

    Every field is optional; at least one of ``username``/``new_password``/
    ``new_access_code`` must be supplied. ``current_password`` (and any
    other field a future verification provider requires — see
    ``apps.accounts.verification``) is the verification factor, checked
    BEFORE anything is written.

    Nothing here is ever echoed back: the response carries only the safe
    ``UserManagementSerializer`` shape plus which fields changed. No
    password or access code, current or new, appears in any response.
    """

    username = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=150)
    new_password = serializers.CharField(required=False, write_only=True, trim_whitespace=False, min_length=8)
    new_access_code = serializers.CharField(required=False, write_only=True, trim_whitespace=False, min_length=6)
    current_password = serializers.CharField(required=False, write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if not any(key in attrs for key in ("username", "new_password", "new_access_code")):
            raise serializers.ValidationError(
                "Supply at least one of: username, new_password, new_access_code."
            )
        return attrs


class SecuritySettingsResponseSerializer(serializers.Serializer):
    """Output-only shape of ``POST /api/v1/auth/settings/security/``."""

    updated_fields = serializers.ListField(child=serializers.CharField())
    user = UserManagementSerializer()


class StaffProfileSerializer(serializers.Serializer):
    """Output-only: documents ``GET /api/v1/auth/users/<id>/profile/``'s
    response for drf-spectacular. The payload itself is built by
    ``apps.accounts.profiles.build_staff_profile()`` (plain dicts computed
    from existing ledgers, never a model instance), so this class exists
    for the schema, not for serialization.
    """

    profile = serializers.DictField()
    lead_performance = serializers.DictField()
    converted_customers = serializers.ListField(child=serializers.DictField())
    interaction_history = serializers.ListField(child=serializers.DictField())
    work_activity = serializers.DictField()
    managed_employees = serializers.ListField(child=serializers.DictField())
    scope_lead_stats = serializers.DictField(allow_null=True)


class SecurityVerificationMethodSerializer(serializers.Serializer):
    """Output-only: ``GET /api/v1/auth/settings/security/`` — what the
    configured verification provider needs before a security change is
    accepted (see ``apps.accounts.verification.describe_security_verification()``).
    """

    method = serializers.CharField()
    required_fields = serializers.ListField(child=serializers.CharField())
