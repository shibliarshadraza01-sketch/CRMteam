"""CP19: verifies OpenAPI schema generation covers the system API with
zero warnings — mirrors every prior checkpoint's test_openapi.py. Schema
generation introspects already-loaded views/serializers; it does not
query the database.
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
    for resource in ("audit-logs", "settings", "feature-flags", "background-jobs"):
        assert f"/api/v1/system/{resource}/" in paths
        assert f"/api/v1/system/{resource}/{{id}}/" in paths


def test_schema_includes_restore_and_hard_delete_for_writable_resources():
    schema = _generate()
    paths = schema["paths"]
    for resource in ("settings", "feature-flags", "background-jobs"):
        assert f"/api/v1/system/{resource}/{{id}}/restore/" in paths
        assert f"/api/v1/system/{resource}/{{id}}/hard-delete/" in paths


def test_schema_excludes_restore_and_hard_delete_for_audit_logs():
    """AuditLog has no soft-delete support at all — see views.py's
    docstring. Same verification shape as every prior read-only-model
    check since CP15's CommunicationLog.
    """
    schema = _generate()
    paths = schema["paths"]
    assert "/api/v1/system/audit-logs/{id}/restore/" not in paths
    assert "/api/v1/system/audit-logs/{id}/hard-delete/" not in paths


def test_schema_includes_backgroundjob_lifecycle_actions():
    schema = _generate()
    paths = schema["paths"]
    assert "/api/v1/system/background-jobs/{id}/start/" in paths
    assert "/api/v1/system/background-jobs/{id}/complete/" in paths
    assert "/api/v1/system/background-jobs/{id}/fail/" in paths


def test_schema_generation_produces_no_warnings():
    from drf_spectacular.drainage import GENERATOR_STATS, reset_generator_stats

    reset_generator_stats()
    _generate()
    assert len(GENERATOR_STATS._warn_cache) == 0
    assert len(GENERATOR_STATS._error_cache) == 0
