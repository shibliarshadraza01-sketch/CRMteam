"""CP10: verifies OpenAPI schema generation covers the CRM API with zero
warnings — the same generator ``manage.py spectacular`` uses, invoked
in-process. Schema generation introspects views/serializers/URL patterns
already loaded in memory; it does not query the database.
"""
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema


def _generate():
    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)
    return schema


def test_schema_generates_without_raising():
    schema = _generate()
    assert schema is not None


def test_schema_validates_as_openapi():
    schema = _generate()
    validate_schema(schema)  # raises if the schema is structurally invalid


def test_schema_includes_every_crm_path():
    schema = _generate()
    paths = schema["paths"]
    for resource in ("customers", "leads", "contacts", "addresses", "opportunities"):
        assert f"/api/v1/crm/{resource}/" in paths
        assert f"/api/v1/crm/{resource}/{{id}}/" in paths


def test_schema_includes_every_cp11_opportunity_action():
    schema = _generate()
    paths = schema["paths"]
    for action in ("advance-stage", "mark-won", "mark-lost", "reopen", "notes", "activities"):
        path = f"/api/v1/crm/opportunities/{{id}}/{action}/"
        assert path in paths, f"{path} missing from schema"


def test_schema_customer_and_lead_status_enums_do_not_collide():
    schema = _generate()
    component_names = set(schema.get("components", {}).get("schemas", {}).keys())
    assert "CustomerStatusEnum" in component_names
    assert "LeadStatusEnum" in component_names
    # Neither collided into an unstable hash-suffixed name.
    assert not any(name.startswith("Status") and name != "Status" for name in component_names if "Enum" not in name)


def test_schema_generation_produces_no_warnings():
    """Mirrors what ``manage.py spectacular`` actually checks: after fixing
    the Customer/Lead ``status`` enum-naming collision (see
    ``ENUM_NAME_OVERRIDES`` in settings), generating the schema for the
    whole project — CRM's new endpoints included — produces zero warnings.
    ``GENERATOR_STATS`` (``drf_spectacular.drainage``) is the actual
    singleton ``manage.py spectacular``'s own summary output reads from.
    """
    from drf_spectacular.drainage import GENERATOR_STATS, reset_generator_stats

    reset_generator_stats()
    _generate()
    assert len(GENERATOR_STATS._warn_cache) == 0
    assert len(GENERATOR_STATS._error_cache) == 0
