"""Identity foundation: the CRM's custom User model.

This is CP2's central deliverable. It intentionally contains ONLY identity
fields (email, name, role, status, timestamps) plus what Django's auth
machinery needs to function. It does NOT contain:

- hierarchy fields (manager_id, team_id) -> CP6
- Super Admin secret access-code fields -> CP4 (its own checkpoint)
- device/session authorization fields -> CP5
- full RBAC/permission JSON -> CP6

See BACKEND_LEARNING_GUIDE.md (CP2 section) for the reasoning behind each
design decision below.
"""
from django.contrib.auth.base_user import AbstractBaseUser
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
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
