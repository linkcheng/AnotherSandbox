"""cap-code / cap-jupyter 反代可达性 E2E。

对应 spec.md FR-024 / FR-025 / FR-031；tasks.md T040。
"""
from __future__ import annotations

import pytest
import httpx


@pytest.mark.smoke
def test_code_server_via_nginx(client: httpx.Client) -> None:
    """/code-server/ 反代到 cap-code:8081 非 5xx。"""
    response = client.get("/code-server/", follow_redirects=False)
    assert response.status_code < 500, f"cap-code 不可用: {response.status_code}"


@pytest.mark.smoke
def test_jupyter_via_nginx(client: httpx.Client) -> None:
    """/jupyter/ 反代到 cap-jupyter:8888 非 5xx。"""
    response = client.get("/jupyter/api/status", follow_redirects=False)
    assert response.status_code < 500, f"cap-jupyter 不可用: {response.status_code}"
