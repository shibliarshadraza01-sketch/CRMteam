"""CP18: verifies OpenAPI schema generation covers the integrations API
with zero warnings — mirrors every prior checkpoint's test_openapi.py.
Schema generation introspects already-loaded views/serializers; it does
not query the database.
"""
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema


def _generate():
    return SchemaGenerator().get_schema(request=None, public=True)


def test_schema_generates_without_raising():
    assert _generate() is not None


def test_schema_validates_as_openapi():
    validate_schema(_generate())


def test_schema_includes_every_router_registered_resource():
    schema = _generate()
    paths = schema["paths"]
    for resource in ("integrations", "api-keys", "webhook-endpoints", "webhook-deliveries"):
        assert f"/api/v1/integrations/{resource}/" in paths
        assert f"/api/v1/integrations/{resource}/{{id}}/" in paths


def test_schema_includes_restore_and_hard_delete_for_writable_resources():
    schema = _generate()
    paths = schema["paths"]
    for resource in ("integrations", "api-keys", "webhook-endpoints"):
        assert f"/api/v1/integrations/{resource}/{{id}}/restore/" in paths
        assert f"/api/v1/integrations/{resource}/{{id}}/hard-delete/" in paths


def test_schema_excludes_restore_and_hard_delete_for_webhook_deliveries():
    schema = _generate()
    paths = schema["paths"]
    assert "/api/v1/integrations/webhook-deliveries/{id}/restore/" not in paths
    assert "/api/v1/integrations/webhook-deliveries/{id}/hard-delete/" not in paths


def test_schema_includes_custom_actions():
    schema = _generate()
    paths = schema["paths"]
    assert "/api/v1/integrations/api-keys/{id}/rotate/" in paths
    assert "/api/v1/integrations/api-keys/{id}/revoke/" in paths
    assert "/api/v1/integrations/webhook-endpoints/{id}/regenerate-secret/" in paths
    assert "/api/v1/integrations/webhook-endpoints/{id}/deliver/" in paths


def test_apikey_schema_never_documents_key_hash_or_raw_key_on_plain_serializer():
    schema = _generate()
    api_key_schema = schema["components"]["schemas"]["APIKey"]["properties"]
    assert "key_hash" not in api_key_schema
    assert "raw_key" not in api_key_schema


def test_schema_generation_produces_no_warnings():
    from drf_spectacular.drainage import GENERATOR_STATS, reset_generator_stats

    reset_generator_stats()
    _generate()
    assert len(GENERATOR_STATS._warn_cache) == 0
    assert len(GENERATOR_STATS._error_cache) == 0
