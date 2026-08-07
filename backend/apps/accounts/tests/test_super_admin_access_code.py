"""CP4: Super Admin secondary access-code and challenge-token logic.

Deliberately written to need NO database connection: User.set_access_code()/
check_access_code() operate purely on an in-memory model instance (no query
involved), and the challenge helpers in apps/accounts/challenge.py are pure
signing functions. Unlike every CP2/CP3 test (all blocked on the missing
PostgreSQL instance — see BACKEND_PROGRESS.md), these tests actually RUN and
PASS in this environment, and are real, verified evidence the CP4 hashing/
signing logic itself is correct. The full HTTP-level integration tests (which
DO need the database) live in test_super_admin_auth.py.
"""
import types

import pytest
from django.core import signing
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.accounts.challenge import issue_super_admin_challenge, read_super_admin_challenge

User = get_user_model()


def _unsaved_super_admin(**extra):
    return User(email="admin@example.com", role=User.Role.SUPER_ADMIN, **extra)


# --------------------------------------------------------------------------
# set_access_code() / check_access_code()
# --------------------------------------------------------------------------


def test_set_access_code_stores_a_hash_not_the_raw_code():
    user = _unsaved_super_admin()
    user.set_access_code("correct-horse-battery-staple")

    assert user.super_admin_access_code_hash != "correct-horse-battery-staple"
    assert user.super_admin_access_code_hash  # non-empty
    # Django hasher output is self-describing, same family used for the
    # primary password (see BACKEND_LEARNING_GUIDE.md CP2, "Django password
    # hashing").
    assert user.super_admin_access_code_hash.startswith("pbkdf2_sha256$")


def test_set_access_code_rejects_empty_code():
    user = _unsaved_super_admin()

    with pytest.raises(ValueError):
        user.set_access_code("")


def test_check_access_code_correct():
    user = _unsaved_super_admin()
    user.set_access_code("correct-code-123")

    assert user.check_access_code("correct-code-123") is True


def test_check_access_code_wrong():
    user = _unsaved_super_admin()
    user.set_access_code("correct-code-123")

    assert user.check_access_code("wrong-code") is False


def test_check_access_code_empty_submission():
    user = _unsaved_super_admin()
    user.set_access_code("correct-code-123")

    assert user.check_access_code("") is False


def test_check_access_code_when_none_configured():
    user = _unsaved_super_admin()  # super_admin_access_code_hash defaults to ""

    assert user.check_access_code("anything") is False


def test_check_access_code_fails_closed_for_non_super_admin():
    """Even if a hash were somehow present, a non-SUPER_ADMIN never verifies.

    Simulates a stale hash surviving in memory on a non-Super-Admin instance
    (the save()-time invariant normally prevents this from ever being
    persisted — see test_role_demotion_clears_hash_on_save in
    test_super_admin_auth.py — but check_access_code() must fail closed
    regardless, as defense in depth).
    """
    throwaway = _unsaved_super_admin()
    throwaway.set_access_code("some-code")

    user = User(email="mgr@example.com", role=User.Role.MANAGER)
    user.super_admin_access_code_hash = throwaway.super_admin_access_code_hash

    assert user.check_access_code("some-code") is False


def test_changing_the_code_invalidates_the_old_one():
    user = _unsaved_super_admin()
    user.set_access_code("first-code")
    assert user.check_access_code("first-code") is True

    user.set_access_code("second-code")

    assert user.check_access_code("first-code") is False
    assert user.check_access_code("second-code") is True


def test_access_code_hash_never_appears_in_user_serializer():
    from apps.accounts.serializers import UserSerializer

    user = _unsaved_super_admin(id=1, first_name="", last_name="")
    user.set_access_code("super-secret-code")

    data = UserSerializer(user).data

    assert "super_admin_access_code_hash" not in data
    assert set(data.keys()) == {"id", "email", "first_name", "last_name", "role"}


# --------------------------------------------------------------------------
# Challenge token (django.core.signing) — issue/read
# --------------------------------------------------------------------------


def test_issue_and_read_challenge_roundtrip():
    fake_user = types.SimpleNamespace(pk=42)

    token = issue_super_admin_challenge(fake_user)
    payload = read_super_admin_challenge(token)

    assert payload == {"user_id": 42}


def test_challenge_token_is_not_jwt_shaped():
    """Structurally distinct from a SimpleJWT token (STEP 6): a JWT is
    exactly 3 dot-separated segments; django.core.signing output is not.
    """
    fake_user = types.SimpleNamespace(pk=1)
    token = issue_super_admin_challenge(fake_user)

    assert token.count(".") != 2 or ":" in token  # signing.dumps uses ':' separators, not JWT's 3-part dot format


def test_challenge_token_contains_no_password_or_access_code():
    fake_user = types.SimpleNamespace(pk=7)
    token = issue_super_admin_challenge(fake_user)

    # signing does not encrypt (only authenticates) — the payload is legible
    # once base64-decoded, so this also documents that nothing besides the
    # user id is ever put in it.
    payload = signing.loads(token, salt="apps.accounts.super_admin_challenge")
    assert set(payload.keys()) == {"user_id"}


def test_malformed_challenge_raises_bad_signature():
    with pytest.raises(signing.BadSignature):
        read_super_admin_challenge("not-a-real-token")


def test_tampered_challenge_raises_bad_signature():
    fake_user = types.SimpleNamespace(pk=1)
    token = issue_super_admin_challenge(fake_user)
    tampered = token[:-1] + ("x" if token[-1] != "x" else "y")

    with pytest.raises(signing.BadSignature):
        read_super_admin_challenge(tampered)


def test_expired_challenge_raises_signature_expired():
    fake_user = types.SimpleNamespace(pk=1)
    token = issue_super_admin_challenge(fake_user)

    with override_settings(SUPER_ADMIN_CHALLENGE_TTL_SECONDS=0):
        with pytest.raises(signing.SignatureExpired):
            read_super_admin_challenge(token)


def test_challenge_salt_namespaces_against_other_signed_values():
    """A value signed for an unrelated purpose must not be accepted here."""
    unrelated_token = signing.dumps({"user_id": 1}, salt="some.other.purpose")

    with pytest.raises(signing.BadSignature):
        read_super_admin_challenge(unrelated_token)
