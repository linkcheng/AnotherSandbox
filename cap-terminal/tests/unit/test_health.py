"""cap-terminal /api/v1/health 端点单元测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """GET /api/v1/health 返回 200 与 {"status": "ok"}。"""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_idempotent(client: TestClient) -> None:
    """连续两次调用 health 端点行为一致（幂等）。"""
    first = client.get("/api/v1/health")
    second = client.get("/api/v1/health")

    assert first.json() == second.json() == {"status": "ok"}
