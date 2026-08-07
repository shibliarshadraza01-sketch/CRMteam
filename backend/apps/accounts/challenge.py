"""CP4: the Super Admin secondary-authentication challenge token.

A narrow, single-purpose helper: issue and read a short-lived, signed token
that bridges primary email/password login and the secondary access-code
verify step for SUPER_ADMIN users.

This is deliberately built on ``django.core.signing`` — NOT SimpleJWT — so it
is structurally incapable of being mistaken for, or accepted as, a JWT access
or refresh token:

- It carries no ``token_type``/``exp`` JWT claims and is not a JWT at all
  (three dot-separated base64url segments); ``django.core.signing`` produces
  a completely different string shape.
- SimpleJWT's ``JWTAuthentication`` tries to parse the ``Authorization:
  Bearer`` value as a JWT; a signing.dumps() string fails that parse
  immediately and is rejected, not silently accepted.
- SimpleJWT's ``TokenRefreshView`` similarly expects a JWT-shaped refresh
  token and rejects this format outright.

Signing uses ``SECRET_KEY`` (Django's default signing key) — no second secret
was introduced, matching CP3's SimpleJWT SIGNING_KEY decision. See
BACKEND_LEARNING_GUIDE.md CP4 for the full rationale.
"""
from django.conf import settings
from django.core import signing

# A distinct salt namespaces this signer from any other use of Django's
# signing framework elsewhere in the project, and is itself mixed into the
# signature — so a validly-signed value from a *different* purpose could
# never be replayed here even if the raw SECRET_KEY were shared (which it
# always is, by design).
_SALT = "apps.accounts.super_admin_challenge"


def issue_super_admin_challenge(user):
    """Return a signed challenge token identifying `user`.

    Contains only the user's primary key — never a password, access code, or
    any other secret material.
    """
    return signing.dumps({"user_id": user.pk}, salt=_SALT)


def read_super_admin_challenge(token):
    """Verify and decode a challenge token.

    Returns the payload dict on success. Raises
    ``django.core.signing.BadSignature`` (covers malformed/tampered tokens)
    or ``django.core.signing.SignatureExpired`` (a well-formed but expired
    token) on failure — callers are expected to catch both and fail safely.
    """
    max_age = settings.SUPER_ADMIN_CHALLENGE_TTL_SECONDS
    return signing.loads(token, salt=_SALT, max_age=max_age)
