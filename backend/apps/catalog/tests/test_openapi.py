"""CP13: verifies OpenAPI schema generation covers the catalog API with
zero warnings — mirrors the approach every prior checkpoint's
test_openapi.py uses. Schema generation introspects already-loaded
views/serializers; it does not query the database.
"""
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema


def _generate():
    return SchemaGenerator().get_schema(request=None, public=True)


def test_schema_generates_without_raising():
    assert _generate() is not None


def test_schema_validates_as_openapi():
    validate_schema(_generate())


def test_schema_includes_every_catalog_path():
    schema = _generate()
    paths = schema["paths"]
    for resource in ("products", "services", "pricebooks", "pricebook-entries"):
        assert f"/api/v1/catalog/{resource}/" in paths
        assert f"/api/v1/catalog/{resource}/{{id}}/" in paths


def test_schema_includes_restore_and_hard_delete_for_every_resource():
    schema = _generate()
    paths = schema["paths"]
    for resource in ("products", "services", "pricebooks", "pricebook-entries"):
        assert f"/api/v1/catalog/{resource}/{{id}}/restore/" in paths
        assert f"/api/v1/catalog/{resource}/{{id}}/hard-delete/" in paths


def test_schema_generation_produces_no_warnings():
    from drf_spectacular.drainage import GENERATOR_STATS, reset_generator_stats

    reset_generator_stats()
    _generate()
    assert len(GENERATOR_STATS._warn_cache) == 0
    assert len(GENERATOR_STATS._error_cache) == 0
