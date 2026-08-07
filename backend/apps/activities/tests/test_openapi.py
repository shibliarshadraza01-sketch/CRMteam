"""CP14: verifies OpenAPI schema generation covers the activities API with
zero warnings — mirrors every prior checkpoint's test_openapi.py. Schema
generation introspects already-loaded views/serializers; it does not query
the database.
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
    for resource in ("tasks", "events", "activity-logs", "reminders"):
        assert f"/api/v1/activities/{resource}/" in paths
        assert f"/api/v1/activities/{resource}/{{id}}/" in paths


def test_schema_includes_restore_and_hard_delete_for_every_resource():
    schema = _generate()
    paths = schema["paths"]
    for resource in ("tasks", "events", "activity-logs", "reminders"):
        assert f"/api/v1/activities/{resource}/{{id}}/restore/" in paths
        assert f"/api/v1/activities/{resource}/{{id}}/hard-delete/" in paths


def test_schema_includes_custom_actions():
    schema = _generate()
    paths = schema["paths"]
    assert "/api/v1/activities/tasks/{id}/complete/" in paths
    assert "/api/v1/activities/tasks/{id}/cancel/" in paths
    assert "/api/v1/activities/tasks/{id}/reassign/" in paths
    assert "/api/v1/activities/events/{id}/occurrences/" in paths
    assert "/api/v1/activities/reminders/{id}/mark-sent/" in paths


def test_schema_includes_timeline_endpoint():
    schema = _generate()
    assert "/api/v1/activities/timeline/" in schema["paths"]


def test_schema_generation_produces_no_warnings():
    from drf_spectacular.drainage import GENERATOR_STATS, reset_generator_stats

    reset_generator_stats()
    _generate()
    assert len(GENERATOR_STATS._warn_cache) == 0
    assert len(GENERATOR_STATS._error_cache) == 0
