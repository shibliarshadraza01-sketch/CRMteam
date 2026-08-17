"""Final-completion-pass: project-wide regression tests proving sensitive
fields (passwords, hashes, tokens, API keys, webhook signing material)
cannot accidentally appear in an API response.

Two complementary techniques:

1. STATIC — every ``ModelSerializer`` subclass in the project is
   introspected via Django's app registry; any ``Meta.fields`` entry whose
   name matches a forbidden pattern (password/hash/secret/token/key,
   allow-listing the few fields deliberately exposed by design) fails the
   test immediately, before a single HTTP request is made. This catches a
   REGRESSION (a future serializer accidentally listing a sensitive field)
   the moment it's introduced, project-wide, without needing a dedicated
   test per app.
2. RUNTIME — representative models with genuinely sensitive fields
   (``User.password``, ``APIKey.key_hash``) are actually serialized and
   the resulting dict is asserted to never contain the raw
   password/hash value.
"""
import importlib
import inspect
import pkgutil

import pytest
from rest_framework import serializers

import apps as apps_package

pytestmark = pytest.mark.django_db

#: Field names that are safe to expose DELIBERATELY, keyed by the exact
#: serializer class name they're allowed on — every other serializer in
#: the project must not have a field matching FORBIDDEN_PATTERNS below.
ALLOWED_EXPOSURES = {
    # Webhook signing secrets are re-viewable by design (Stripe/GitHub
    # convention) — see apps/integrations/serializers.py's own docstring.
    "WebhookEndpointSerializer": {"secret"},
    # The one-time raw API key, returned ONLY at generate/rotate time —
    # never by list/retrieve (a different serializer class entirely).
    "APIKeyWithSecretSerializer": {"raw_key"},
    # write_only=True — accepted on create, never echoed back in a
    # response (see apps/accounts/serializers.py's own docstring).
    "UserCreateSerializer": {"password"},
}

FORBIDDEN_PATTERNS = ("password", "secret", "token", "api_key", "access_code", "webhook_secret", "_hash")


def _iter_serializer_classes():
    """Every ``rest_framework.serializers.ModelSerializer`` subclass
    defined anywhere under ``apps.*.serializers`` — found by walking the
    app registry rather than hardcoding a per-app import list, so a new
    app's serializers are covered automatically.
    """
    for _, app_name, _ in pkgutil.iter_modules(apps_package.__path__):
        try:
            module = importlib.import_module(f"apps.{app_name}.serializers")
        except ModuleNotFoundError:
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, serializers.ModelSerializer) and obj.__module__ == module.__name__:
                yield obj


def test_no_serializer_exposes_a_forbidden_field_name_unless_explicitly_allowed():
    violations = []
    for serializer_class in _iter_serializer_classes():
        meta = getattr(serializer_class, "Meta", None)
        fields = list(getattr(meta, "fields", []) or [])
        # Declared (non-Meta.fields-driven) attributes count too — e.g. a
        # field added directly on the class body rather than relying on
        # ModelSerializer's auto-generation from Meta.fields.
        fields += [
            name
            for name, value in vars(serializer_class).items()
            if isinstance(value, serializers.Field) and not name.startswith("_")
        ]

        allowed = ALLOWED_EXPOSURES.get(serializer_class.__name__, set())
        for field_name in fields:
            if field_name in allowed:
                continue
            lowered = field_name.lower()
            if any(pattern in lowered for pattern in FORBIDDEN_PATTERNS):
                violations.append(f"{serializer_class.__module__}.{serializer_class.__name__}: '{field_name}'")

    assert not violations, "Serializers exposing forbidden field names:\n" + "\n".join(violations)


def test_user_serializer_output_never_contains_the_password_hash(django_user_model):
    from apps.accounts.serializers import UserSerializer

    user = django_user_model.objects.create_user(email="secret-check@example.com", password="a-strong-password-1")
    data = UserSerializer(user).data

    assert "password" not in data
    serialized_values = [str(value) for value in data.values()]
    assert not any(user.password in value for value in serialized_values)


def test_api_key_serializer_output_never_contains_the_key_hash():
    from apps.integrations.models import APIKey, Integration
    from apps.integrations.serializers import APIKeySerializer
    from apps.integrations.services import generate_api_key

    integration = Integration.objects.create(name="Test Integration")
    api_key, raw_key = generate_api_key(integration, name="Test Key")

    data = APIKeySerializer(api_key).data

    assert "key_hash" not in data
    assert "raw_key" not in data
    serialized_values = [str(value) for value in data.values()]
    assert not any(api_key.key_hash in value for value in serialized_values)
    assert not any(raw_key in value for value in serialized_values)


def test_super_admin_access_code_hash_never_appears_in_user_serializer_output(django_user_model):
    from apps.accounts.serializers import UserSerializer

    user = django_user_model.objects.create_user(
        email="super-admin-secret-check@example.com",
        password="a-strong-password-1",
        role=django_user_model.Role.SUPER_ADMIN,
    )
    user.set_access_code("a-secret-access-code-1")
    user.save()

    data = UserSerializer(user).data

    assert "super_admin_access_code_hash" not in data
    serialized_values = [str(value) for value in data.values()]
    assert not any(user.super_admin_access_code_hash in value for value in serialized_values)
