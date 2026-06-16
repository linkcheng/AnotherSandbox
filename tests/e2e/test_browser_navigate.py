"""cap-mcp browser_navigate 端到端测试。

对应 spec.md FR-031；tasks.md T064。
前置：`make up` 已启动完整 stack（含 cap-browser Chromium）。
"""
from __future__ import annotations

import pytest
import httpx


@pytest.mark.browser
def test_browser_navigate_via_mcp(client: httpx.Client) -> None:
    """MCP browser_navigate 操作共享 Chromium，返回 ok + title。"""
    response = client.post(
        "/mcp/sandbox/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "browser_navigate",
                "arguments": {"url": "https://example.com"},
            },
        },
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    assert response.status_code == 200
    body = response.json()
    assert "result" in body or "content" in body
