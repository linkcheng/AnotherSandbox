"""cap-mcp shell_exec 端到端测试。

对应 spec.md FR-031 / SC-005；tasks.md T058。
前置：`make up` 已启动完整 stack（cap-nginx → cap-mcp → cap-agent → cap-terminal）。
"""
from __future__ import annotations

import httpx
import pytest


@pytest.mark.shell
def test_shell_exec_via_mcp(client: httpx.Client) -> None:
    """MCP shell_exec 经 cap-nginx 反代到 cap-mcp，最终在 tmux 执行。"""
    response = client.post(
        "/mcp/sandbox/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "shell_exec",
                "arguments": {"command": "echo hello"},
            },
        },
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )

    assert response.status_code == 200
    body = response.json()
    # Streamable HTTP 可能返回 {"result": {"content": [...]}} 或直接 content
    assert "result" in body or "content" in body
