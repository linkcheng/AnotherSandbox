"""cap-agent /v1/health E2E 冒烟测试（US1 阶段启用）。

对应 spec.md FR-016 / FR-031 / SC-002；tasks.md T037。
"""
from __future__ import annotations

import pytest
import httpx


@pytest.mark.smoke
def test_agent_health_via_nginx(client: httpx.Client) -> None:
    """通过 cap-nginx 反代访问 cap-agent /v1/health 返回 ok。

    前置：`make up` 已启动完整 stack。
    """
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
