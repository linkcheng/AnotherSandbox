"""cap-mcp shell_exec 工具单元测试。

对应 spec.md FR-027、FR-028；tasks.md T054；contracts/cap-mcp-tools.md。
"""
from __future__ import annotations

import json
import os

import httpx
import pytest
import respx

# cap-mcp 默认 agent_url
os.environ.setdefault("CAP_MCP_AGENT_URL", "http://cap-agent:9000")


@pytest.mark.asyncio
async def test_shell_exec_calls_agent() -> None:
    """shell_exec 转发到 cap-agent:9000/v1/shell/exec。"""
    from cap_mcp.tools.shell import shell_exec

    agent_response = {
        "exit_code": 0,
        "stdout": "hello\n",
        "stderr": "",
        "duration_ms": 12,
    }
    with respx.mock(base_url="http://cap-agent:9000") as mock:
        mock.post("/v1/shell/exec").mock(
            return_value=httpx.Response(200, json=agent_response)
        )

        result = await shell_exec("echo hello")

    assert result["exit_code"] == 0
    assert result["stdout"] == "hello\n"


@pytest.mark.asyncio
async def test_shell_exec_forwards_timeout() -> None:
    """timeout_s 参数透传到 cap-agent。"""
    from cap_mcp.tools.shell import shell_exec

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        route = mock.post("/v1/shell/exec").mock(
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
        await shell_exec("sleep 1", timeout_s=1)

    body = json.loads(route.calls.last.request.content)
    assert body["command"] == "sleep 1"
    assert body["timeout_s"] == 1


@pytest.mark.asyncio
async def test_shell_exec_upstream_error_returns_error_dict() -> None:
    """cap-agent 返回非 2xx 时返回 exit_code 非 0 + stderr 提示。

    不抛异常，让 MCP 客户端处理错误。
    """
    from cap_mcp.tools.shell import shell_exec

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        mock.post("/v1/shell/exec").mock(return_value=httpx.Response(503))

        result = await shell_exec("echo")

    assert result["exit_code"] != 0
    assert "error" in result["stderr"].lower() or "503" in result["stderr"]


@pytest.mark.asyncio
async def test_shell_exec_upstream_unreachable_returns_error_dict() -> None:
    """cap-agent 连接失败时返回错误字典。"""
    from cap_mcp.tools.shell import shell_exec

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        mock.post("/v1/shell/exec").mock(
            side_effect=httpx.ConnectError("unreachable")
        )

        result = await shell_exec("echo")

    assert result["exit_code"] != 0
    assert "unavailable" in result["stderr"].lower() or "error" in result["stderr"].lower()


@pytest.mark.asyncio
async def test_shell_exec_returns_all_fields() -> None:
    """返回值含全部 4 个字段。"""
    from cap_mcp.tools.shell import shell_exec

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        mock.post("/v1/shell/exec").mock(
            return_value=httpx.Response(
                200,
                json={
                    "exit_code": 0,
                    "stdout": "ok",
                    "stderr": "",
                    "duration_ms": 5,
                },
            )
        )
        result = await shell_exec("echo ok")

    assert set(result.keys()) == {"exit_code", "stdout", "stderr", "duration_ms"}
