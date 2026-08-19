"""Staff-management pass: the security-change verification ABSTRACTION.

The spec requires that before ANY security-sensitive Super Admin setting
is saved (username, password, secondary access code) the backend runs a
verification step — and that the step be a real, pluggable seam today
rather than a fake "we sent you an OTP" that always succeeds.

That is exactly what this module is: one provider interface
(``SecurityVerificationProvider``), one deliberately-strict default
implementation, and one module-level entry point
(``verify_security_change()`` — the backend counterpart of the spec's
``verifySecurityChange()``) that every security-sensitive write goes
through.

Design rules, each deliberate:

- **Never fake success.** The default provider does NOT approve a change
  just because a challenge string was posted. It requires the caller to
  re-present their CURRENT password (``current_password``) — a real,
  already-implemented factor this project genuinely owns — and nothing
  weaker. A future OTP/email/auth-app provider replaces it without any
  caller changing.
- **Never block startup.** Selecting a provider reads an environment
  variable at CALL time, not import time, and an unknown/unavailable
  provider name falls back to the built-in password re-entry provider
  instead of raising. No external credential is ever required for the
  backend to boot, migrate, or serve (see the deployment-readiness rule
  in this project's own settings modules).
- **Fail closed.** Anything the provider cannot positively verify raises
  ``SecurityVerificationRequired``, which the API layer surfaces as a
  403 — never a silent pass.

Plugging in a real second factor later means: write a class with a
``verify(user, change_type, payload) -> None`` method that raises
``SecurityVerificationRequired`` on failure, register it in
``PROVIDERS``, and set ``SECURITY_VERIFICATION_PROVIDER`` in the
environment. No call site changes.
"""
import os

from rest_framework.exceptions import PermissionDenied


class SecurityVerificationRequired(PermissionDenied):
    """Raised when a security-sensitive change could not be verified.

    Subclasses DRF's ``PermissionDenied`` so any view that does not catch
    it still produces a correct 403 through DRF's own exception handler,
    exactly like ``apps.crm.services.OwnerAssignmentNotAllowed`` already
    does for owner assignment.
    """

    default_detail = "This change requires security verification."


#: The change types this project recognizes. Passed to the provider so a
#: future implementation can require a stronger factor for some changes
#: than others (e.g. an access-code change vs. a display-name change).
CHANGE_PASSWORD = "password"
CHANGE_USERNAME = "username"
CHANGE_ACCESS_CODE = "access_code"

CHANGE_TYPES = (CHANGE_PASSWORD, CHANGE_USERNAME, CHANGE_ACCESS_CODE)


class SecurityVerificationProvider:
    """Interface every verification method implements."""

    #: Short machine name, echoed to clients so a UI can render the right
    #: prompt ("enter your password", "enter the code we emailed you", ...).
    name = "base"

    def describe(self):
        """Metadata a frontend needs to render the verification step.

        ``required_fields`` names the request-body keys the provider will
        look for inside ``payload``.
        """
        return {"method": self.name, "required_fields": []}

    def verify(self, user, change_type, payload):  # pragma: no cover - interface
        raise NotImplementedError


class CurrentPasswordVerificationProvider(SecurityVerificationProvider):
    """Default provider: re-present the account's CURRENT password.

    Not a placeholder that always passes — this is a genuine (if modest)
    re-authentication using machinery this project already owns, so the
    seam is safe to ship before any OTP/email/auth-app provider exists.
    """

    name = "current_password"

    def describe(self):
        return {"method": self.name, "required_fields": ["current_password"]}

    def verify(self, user, change_type, payload):
        current_password = (payload or {}).get("current_password") or ""
        if not current_password or not user.check_password(current_password):
            raise SecurityVerificationRequired(
                "Security verification failed: your current password is required and must be correct."
            )


#: Registry of available providers, keyed by the value
#: ``SECURITY_VERIFICATION_PROVIDER`` may be set to.
PROVIDERS = {
    CurrentPasswordVerificationProvider.name: CurrentPasswordVerificationProvider,
}

DEFAULT_PROVIDER_NAME = CurrentPasswordVerificationProvider.name


def get_verification_provider():
    """Resolve the configured provider, falling back to the default.

    Read at call time (not import time) so tests and future deployments
    can switch providers without reimporting, and so an unset/misspelled
    environment variable degrades to the safe built-in instead of
    breaking startup.
    """
    name = os.environ.get("SECURITY_VERIFICATION_PROVIDER", DEFAULT_PROVIDER_NAME)
    provider_class = PROVIDERS.get(name, PROVIDERS[DEFAULT_PROVIDER_NAME])
    return provider_class()


def describe_security_verification():
    """What the frontend needs to render the verification step."""
    return get_verification_provider().describe()


def verify_security_change(user, change_type, payload=None):
    """The single entry point every security-sensitive write calls first.

    Raises ``SecurityVerificationRequired`` (a 403) unless the configured
    provider positively verifies the request. Returns ``None`` on success.
    """
    if change_type not in CHANGE_TYPES:
        raise SecurityVerificationRequired(f"Unknown security change type: {change_type!r}.")
    get_verification_provider().verify(user, change_type, payload or {})


__all__ = [
    "SecurityVerificationRequired",
    "SecurityVerificationProvider",
    "CurrentPasswordVerificationProvider",
    "CHANGE_PASSWORD",
    "CHANGE_USERNAME",
    "CHANGE_ACCESS_CODE",
    "CHANGE_TYPES",
    "PROVIDERS",
    "get_verification_provider",
    "describe_security_verification",
    "verify_security_change",
]
