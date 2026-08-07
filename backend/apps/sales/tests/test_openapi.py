"""CP12: verifies OpenAPI schema generation covers the sales API with zero
warnings — mirrors apps/crm/tests/test_openapi.py's approach (CP10/CP11).
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


def test_schema_includes_every_sales_path():
    schema = _generate()
    paths = schema["paths"]
    for resource in ("quotes", "invoices", "quote-items", "invoice-items"):
        assert f"/api/v1/sales/{resource}/" in paths
        assert f"/api/v1/sales/{resource}/{{id}}/" in paths


def test_schema_includes_every_cp12_custom_action():
    schema = _generate()
    paths = schema["paths"]
    for action in ("submit", "approve", "reject", "convert"):
        assert f"/api/v1/sales/quotes/{{id}}/{action}/" in paths
    for action in ("mark-paid", "cancel"):
        assert f"/api/v1/sales/invoices/{{id}}/{action}/" in paths


def test_schema_quote_and_invoice_status_enums_do_not_collide():
    schema = _generate()
    component_names = set(schema.get("components", {}).get("schemas", {}).keys())
    assert "QuoteStatusEnum" in component_names
    assert "InvoiceStatusEnum" in component_names


def test_schema_generation_produces_no_warnings():
    from drf_spectacular.drainage import GENERATOR_STATS, reset_generator_stats

    reset_generator_stats()
    _generate()
    assert len(GENERATOR_STATS._warn_cache) == 0
    assert len(GENERATOR_STATS._error_cache) == 0
