"""Identity foundation: the CRM's custom User model, plus (CP5) UserSession.

CP2's identity fields (email, name, role, status, timestamps) plus what
Django's auth machinery needs to function. CP4 added the Super Admin
secondary access-code hash. CP5 adds ``UserSession`` — a persistent record of
each issued refresh token, letting a user see and revoke their own active
sessions/devices. ``User`` itself still does NOT contain:

- hierarchy fields (manager_id, team_id) -> CP6
- full RBAC/permission JSON -> CP6

See BACKEND_LEARNING_GUIDE.md (CP2 section for the base model, CP4 section
for the access-code design, CP5 section for UserSession) for the reasoning
behind each decision below.
"""
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """The CRM's identity model.

    Login is by email (USERNAME_FIELD = "email"), not username.
    AbstractBaseUser supplies ``password`` (always hashed, never raw) and
    ``last_login``. PermissionsMixin supplies ``is_superuser``, ``groups``,
    ``user_permissions``, and the ``has_perm``/``has_perms`` machinery that
    the Django admin site relies on.
    """

    class Role(models.TextChoices):
        """The three roles the client's hierarchy begins with.

        This is identity-level only: which "kind" of user this is. It is NOT
        the permission system itself — full RBAC and row-level data scoping
        (what a MANAGER may see of their team, what an EMPLOYEE may see of
        their own assigned leads) is built in CP6 on top of this field.
        """

        SUPER_ADMIN = "SUPER_ADMIN", _("Super Admin")
        MANAGER = "MANAGER", _("Manager")
        EMPLOYEE = "EMPLOYEE", _("Employee")

    email = models.EmailField(_("email address"), max_length=254, unique=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    role = models.CharField(
        _("role"),
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
        db_index=True,
        help_text=_("Identity/role foundation only. Full permissions are enforced starting CP6."),
    )

    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_("Unselect instead of deleting accounts to preserve history/audit integrity."),
    )
    is_staff = models.BooleanField(
        _("Django admin-site access"),
        default=False,
        help_text=_("Whether this user can log into the Django admin site."),
    )

    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    # CP4: the Super Admin secondary access-code, stored as a Django password
    # hash (via make_password()) — never the raw code. Blank ("") means "no
    # secondary credential configured yet", not "empty code accepted" — see
    # check_access_code() below, which explicitly refuses to verify against
    # a blank hash rather than letting check_password() attempt it. Only
    # meaningful for role == SUPER_ADMIN; see the save() invariant below and
    # BACKEND_LEARNING_GUIDE.md CP4, "model invariants".
    super_admin_access_code_hash = models.CharField(
        _("Super Admin access code hash"),
        max_length=128,
        blank=True,
        default="",
        help_text=_(
            "Hashed secondary access code required for full SUPER_ADMIN "
            "authentication (CP4). Set via set_access_code(), never edited "
            "directly. Meaningless for MANAGER/EMPLOYEE users."
        ),
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    # email (USERNAME_FIELD) and password are always required by
    # createsuperuser; nothing else on this model is mandatory, so there is
    # nothing further to list here.
    REQUIRED_FIELDS = []

    class Meta:
        constraints = [
            # Defense in depth: User.save() always lowercases email before
            # writing, so the plain `unique=True` above already behaves as
            # case-insensitive in practice. This functional constraint makes
            # that guarantee hold at the database level even if some future
            # code path (a data migration, a raw insert) ever bypasses
            # save(). Two indexes on email is a small, deliberate cost for
            # that guarantee.
            models.UniqueConstraint(Lower("email"), name="accounts_user_unique_lower_email"),
        ]
        ordering = ["email"]
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        # Invariant (see BACKEND_LEARNING_GUIDE.md CP2, "model invariants"):
        # a Django superuser is always the CRM's SUPER_ADMIN role. This keeps
        # Django's own admin-privilege concept and the CRM's role concept
        # from ever silently disagreeing (e.g. a superuser accidentally left
        # as EMPLOYEE). It only ever promotes toward SUPER_ADMIN — it never
        # touches role for a non-superuser.
        if self.is_superuser:
            self.role = self.Role.SUPER_ADMIN
        # Invariant (CP4, see BACKEND_LEARNING_GUIDE.md "model invariants"):
        # a non-SUPER_ADMIN never carries a secondary access-code hash. If a
        # user's role is (now) anything other than SUPER_ADMIN but a hash is
        # still set — e.g. they were demoted after having one configured —
        # clear it on save rather than leaving a stale, meaningless secret
        # attached to an ordinary account. This runs on every save, so it is
        # self-enforcing regardless of *how* the role changed.
        if self.role != self.Role.SUPER_ADMIN and self.super_admin_access_code_hash:
            self.super_admin_access_code_hash = ""
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    # -- Super Admin secondary access code (CP4) ---------------------------
    #
    # These are the ONLY two methods that ever touch
    # super_admin_access_code_hash. Both use Django's own password-hashing
    # infrastructure (make_password/check_password — the same machinery
    # AbstractBaseUser.set_password()/check_password() use for the primary
    # password) rather than any custom cryptography. See
    # BACKEND_LEARNING_GUIDE.md CP4 for the full rationale.

    def set_access_code(self, raw_code):
        """Hash and store a new Super Admin secondary access code.

        The raw code is used only to compute a hash — it is never assigned
        to any attribute and does not persist past this call returning. This
        does NOT save the model; callers must call .save() themselves (same
        contract as AbstractBaseUser.set_password()).
        """
        if not raw_code:
            raise ValueError("Access code must not be empty.")
        self.super_admin_access_code_hash = make_password(raw_code)

    def check_access_code(self, raw_code):
        """Verify a raw access code against the stored hash.

        Returns False (never raises) if no code is configured, if the
        submitted value is empty, or if the user's role is not currently
        SUPER_ADMIN — the field is meaningless for MANAGER/EMPLOYEE, so
        verification for them always fails closed, even if a stale hash were
        somehow still present.
        """
        if self.role != self.Role.SUPER_ADMIN:
            return False
        if not raw_code or not self.super_admin_access_code_hash:
            return False
        return check_password(raw_code, self.super_admin_access_code_hash)


class UserSession(models.Model):
    """CP5: one row per issued refresh token — a user-visible "device/session".

    Created on every successful authentication (ordinary EMPLOYEE/MANAGER
    login, or a SUPER_ADMIN completing CP4's secondary verification — both
    paths funnel through the same `_issue_token_pair_response()` helper in
    views.py, so there is exactly one place this row is ever created).

    Deliberately does NOT store the refresh token itself, only its JTI
    (`refresh_token_jti`) — the same claim SimpleJWT's own token_blacklist
    app already keys its `OutstandingToken`/`BlacklistedToken` tables on.
    Revoking a session means blacklisting by that JTI (see
    apps/accounts/services.py's `blacklist_by_jti`) and setting
    `is_active=False` — never deleting the row, so a revoked session remains
    visible in its own history rather than silently vanishing.

    A refresh occurring at POST /api/v1/auth/refresh/ (rotation is enabled —
    see CP3) does NOT create a new row: the existing session's
    `refresh_token_jti` is updated to the newly-rotated token's JTI and
    `last_used_at` advances. See BACKEND_LEARNING_GUIDE.md CP5, "why refresh
    doesn't create a new session", for the full reasoning.
    """

    class DeviceType(models.TextChoices):
        DESKTOP = "DESKTOP", _("Desktop")
        MOBILE = "MOBILE", _("Mobile")
        TABLET = "TABLET", _("Tablet")
        UNKNOWN = "UNKNOWN", _("Unknown")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    refresh_token_jti = models.CharField(
        _("refresh token JTI"),
        max_length=255,
        unique=True,
        help_text=_("The 'jti' claim of the refresh token this session tracks. Never the token itself."),
    )
    device_name = models.CharField(_("device name"), max_length=255, blank=True, default="")
    device_type = models.CharField(
        _("device type"), max_length=20, choices=DeviceType.choices, default=DeviceType.UNKNOWN
    )
    browser = models.CharField(_("browser"), max_length=100, blank=True, default="")
    operating_system = models.CharField(_("operating system"), max_length=100, blank=True, default="")
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.TextField(_("raw user agent"), blank=True, default="")

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    last_used_at = models.DateTimeField(_("last used at"), default=timezone.now)
    expires_at = models.DateTimeField(_("expires at"))
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ["-last_used_at"]
        verbose_name = _("user session")
        verbose_name_plural = _("user sessions")
        indexes = [
            models.Index(fields=["user"], name="accounts_session_user_idx"),
            models.Index(fields=["refresh_token_jti"], name="accounts_session_jti_idx"),
            models.Index(fields=["is_active"], name="accounts_session_active_idx"),
            models.Index(fields=["created_at"], name="accounts_session_created_idx"),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.device_name or 'unknown device'}"
