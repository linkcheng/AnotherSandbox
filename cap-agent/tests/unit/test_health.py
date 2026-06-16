"""cap-agent /v1/health 端点单元测试。

对应 spec.md FR-016、tasks.md T012。
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """GET /v1/health 返回 200 与 {"status": "ok"}。"""
    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_has_no_side_effects(client: TestClient) -> None:
    """连续两次调用 health 端点行为一致（幂等）。"""
    first = client.get("/v1/health")
    second = client.get("/v1/health")

    assert first.json() == second.json() == {"status": "ok"}
