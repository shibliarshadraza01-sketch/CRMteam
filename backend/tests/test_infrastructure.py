"""CP1 infrastructure smoke tests.

These verify that the three infrastructure endpoints introduced in CP1 are
wired up correctly:

* ``GET /health``       — liveness probe returning a fixed JSON body.
* ``GET /api/schema/``  — drf-spectacular OpenAPI schema.
* ``GET /api/docs/``    — Swagger UI page rendering that schema.

They are deliberately narrow: no database rows, no auth, no domain logic.
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


def test_health_returns_healthy_json(client):
    """GET /health -> 200 with the exact expected JSON body."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "crm-backend"}


def test_schema_returns_non_empty_openapi(client):
    """GET /api/schema/ -> 200 with a non-empty OpenAPI 3 schema."""
    response = client.get(reverse("schema"))

    assert response.status_code == 200
    # Response body must be non-empty and look like an OpenAPI document.
    assert response.content, "schema response body is empty"
    body = response.content.decode("utf-8", errors="replace")
    assert "openapi" in body.lower()


def test_docs_returns_swagger_page(client):
    """GET /api/docs/ -> 200 returning the Swagger UI HTML page."""
    response = client.get(reverse("swagger-ui"))

    assert response.status_code == 200
    assert response.content, "docs response body is empty"
    body = response.content.decode("utf-8", errors="replace").lower()
    # Swagger UI page references swagger in its markup/assets.
    assert "swagger" in body
