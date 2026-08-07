"""CP17: verifies OpenAPI schema generation covers the workflows API with
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
    for resource in ("workflows", "triggers", "actions", "executions"):
        assert f"/api/v1/workflows/{resource}/" in paths
        assert f"/api/v1/workflows/{resource}/{{id}}/" in paths


def test_schema_includes_restore_and_hard_delete_for_writable_resources():
    schema = _generate()
    paths = schema["paths"]
    for resource in ("workflows", "triggers", "actions"):
        assert f"/api/v1/workflows/{resource}/{{id}}/restore/" in paths
        assert f"/api/v1/workflows/{resource}/{{id}}/hard-delete/" in paths


def test_schema_excludes_restore_and_hard_delete_for_executions():
    """WorkflowExecution is read-only — see views.py's docstring. Same
    verification shape as CP15's CommunicationLog / CP16's
    ReportExecution.
    """
    schema = _generate()
    paths = schema["paths"]
    assert "/api/v1/workflows/executions/{id}/restore/" not in paths
    assert "/api/v1/workflows/executions/{id}/hard-delete/" not in paths


def test_schema_includes_execute_action():
    schema = _generate()
    assert "/api/v1/workflows/workflows/{id}/execute/" in schema["paths"]


def test_workflow_execution_status_shares_the_report_execution_enum_component():
    """CP17's ENUM_NAME_OVERRIDES entry resolves the WorkflowExecution.Status
    / ReportExecution.Status collision by naming ONE shared component —
    confirms that resolution actually took effect in the generated schema,
    not just that generation didn't warn.
    """
    schema = _generate()
    status_schema = schema["components"]["schemas"]["WorkflowExecution"]["properties"]["status"]
    assert status_schema["allOf"][0]["$ref"] == "#/components/schemas/ReportExecutionStatusEnum"


def test_schema_generation_produces_no_warnings():
    from drf_spectacular.drainage import GENERATOR_STATS, reset_generator_stats

    reset_generator_stats()
    _generate()
    assert len(GENERATOR_STATS._warn_cache) == 0
    assert len(GENERATOR_STATS._error_cache) == 0
