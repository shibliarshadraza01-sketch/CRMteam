"""Custom manager for the accounts.User model.

Django's default UserManager assumes a `username` field. Because this CRM
authenticates by email (USERNAME_FIELD = "email"), we need our own manager
that knows how to build a user from an email address instead.
"""
from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    """Manager for the email-based custom User model.

    Responsible for the two supported ways a User row gets created:
    ``create_user`` (a normal CRM user — role is caller-specified, defaults to
    EMPLOYEE) and ``create_superuser`` (a Django/CRM Super Admin, used mainly
    for ``manage.py createsuperuser`` and initial bootstrapping).
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email field is required.")

        email = self.normalize_email(email)
        # Django's normalize_email() only lowercases the domain part (per the
        # email spec, the local part is technically case-sensitive). This CRM
        # wants case-insensitive login/uniqueness, so we lowercase the whole
        # address ourselves before it ever reaches the unique index or the
        # login lookup. See BACKEND_LEARNING_GUIDE.md CP2 section for why.
        email = email.lower()

        user = self.model(email=email, **extra_fields)
        # set_password() runs Django's configured password hasher (PBKDF2 by
        # default) and stores only the resulting hash — never the raw
        # password. See AUTH_PASSWORD_VALIDATORS in settings for the
        # complexity rules enforced when passwords are validated.
        user.set_password(password)
        user.full_clean(exclude=["password"])
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create a normal CRM user.

        Role is whatever the caller passes via ``extra_fields`` (or the
        model's default, EMPLOYEE, if omitted). Never implicitly grants
        Django staff/superuser access.
        """
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        if extra_fields.get("is_superuser"):
            raise ValueError("create_user() cannot create a Django superuser. Use create_superuser().")
        if extra_fields.get("is_staff"):
            raise ValueError("create_user() cannot create a Django staff user. Use create_superuser().")

        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create a Django superuser.

        A Django superuser is, by CP2's invariant, always the CRM's
        SUPER_ADMIN role (see apps/accounts/models.py `User.save()` for where
        that invariant is enforced). ``is_staff``/``is_superuser`` must both be
        True — anything else is a caller mistake and is rejected rather than
        silently "fixed", so misconfiguration fails loudly at creation time.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)
