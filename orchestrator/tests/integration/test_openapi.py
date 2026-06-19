"""T069: OpenAPI/Swagger 验证。FR-021。"""
import pytest

pytestmark = pytest.mark.integration


def test_openapi_contains_all_endpoints(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = set(r.json()["paths"].keys())
    expected = {
        "/healthz", "/readyz",
        "/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/refresh",
        "/api/v1/workspaces", "/api/v1/workspaces/{workspace_id}",
        "/api/v1/workspaces/{workspace_id}/start", "/api/v1/workspaces/{workspace_id}/stop",
        "/api/v1/audit", "/api/v1/audit/ingest", "/api/v1/verify",
    }
    missing = expected - paths
    assert not missing, f"missing endpoints in OpenAPI: {missing}"


def test_docs_swagger_ui_available(client):
    assert client.get("/docs").status_code == 200
