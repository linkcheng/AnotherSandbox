"""cap-agent /v1/shell/exec 转发集成测试。

用 respx mock cap-terminal:7682，断言请求/响应透传。
对应 spec.md FR-017；tasks.md T051。
"""
from __future__ import annotations

import json
import os

import httpx
import respx
from fastapi.testclient import TestClient

# 设置 cap-terminal URL（与 cap-agent config 默认值一致）
os.environ["CAP_AGENT_TERMINAL_URL"] = "http://cap-terminal:7682"


def test_shell_exec_proxies_to_terminal(client: TestClient) -> None:
    """/v1/shell/exec 透传到 cap-terminal /api/v1/exec。"""
    terminal_response = {
        "exit_code": 0,
        "stdout": "hello\n",
        "stderr": "",
        "duration_ms": 12,
    }
    with respx.mock(base_url="http://cap-terminal:7682") as mock:
        mock.post("/api/v1/exec").mock(
            return_value=httpx.Response(200, json=terminal_response)
        )

        response = client.post(
            "/v1/shell/exec",
            json={"command": "echo hello"},
        )

    assert response.status_code == 200
    assert response.json() == terminal_response


def test_shell_exec_forwards_timeout_s(client: TestClient) -> None:
    """timeout_s 参数透传到下游。"""
    with respx.mock(base_url="http://cap-terminal:7682") as mock:
        route = mock.post("/api/v1/exec").mock(
            return_value=httpx.Response(
                200,
                json={
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "timed out",
                    "duration_ms": 1000,
                },
            )
        )
        client.post(
            "/v1/shell/exec", json={"command": "sleep 1", "timeout_s": 1}
        )

    # 验证下游收到的请求 body 含 timeout_s=1
    body = json.loads(route.calls.last.request.content)
    assert body["command"] == "sleep 1"
    assert body["timeout_s"] == 1


def test_shell_exec_upstream_error_returns_502(client: TestClient) -> None:
    """cap-terminal 返回非 2xx 时返回 502 UpstreamError。"""
    with respx.mock(base_url="http://cap-terminal:7682") as mock:
        mock.post("/api/v1/exec").mock(return_value=httpx.Response(503))

        response = client.post("/v1/shell/exec", json={"command": "echo"})

    assert response.status_code == 502


def test_shell_exec_upstream_timeout_returns_502(client: TestClient) -> None:
    """cap-terminal 连接超时时返回 502。"""
    with respx.mock(base_url="http://cap-terminal:7682") as mock:
        mock.post("/api/v1/exec").mock(
            side_effect=httpx.ConnectTimeout("timeout")
        )

        response = client.post("/v1/shell/exec", json={"command": "echo"})

    assert response.status_code == 502


def test_shell_exec_missing_command_returns_422(client: TestClient) -> None:
    """缺 command 字段返回 422（pydantic 校验，不调用下游）。"""
    with respx.mock(base_url="http://cap-terminal:7682", assert_all_called=False) as mock:
        mock.post("/api/v1/exec").mock(return_value=httpx.Response(200))
        response = client.post("/v1/shell/exec", json={})

    assert response.status_code == 422
    # 422 由 pydantic 触发，不应调用下游
    assert not mock.calls
