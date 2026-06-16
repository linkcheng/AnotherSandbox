"""cap-mcp fs_* 跨容器一致性端到端测试。

对应 spec.md FR-031 / SC-006；tasks.md T068。
前置：`make up` 已启动完整 stack。
"""
from __future__ import annotations

import json
import uuid

import pytest
import httpx


def _mcp_call(client: httpx.Client, tool: str, arguments: dict) -> dict:
    """辅助：发起 MCP tools/call。"""
    response = client.post(
        "/mcp/sandbox/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        },
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    return response.json()


@pytest.mark.fs
def test_fs_write_then_read_via_mcp(client: httpx.Client) -> None:
    """fs_write 写入后 fs_read 读取内容一致。"""
    unique = uuid.uuid4().hex[:8]
    path = f"/workspace/shared/test-{unique}.txt"
    content = f"hello-{unique}"

    _mcp_call(client, "fs_write", {"path": path, "content": content})
    read_result = _mcp_call(client, "fs_read", {"path": path})

    # MCP 响应在 result.content[0].text（JSON 编码）
    text = _extract_text(read_result)
    data = json.loads(text)
    assert data["ok"] is True
    assert data["content"] == content


def _extract_text(mcp_response: dict) -> str:
    """从 MCP 标准响应提取 content[0].text。"""
    result = mcp_response.get("result", {})
    content = result.get("content", [])
    if content and isinstance(content, list):
        return content[0].get("text", "{}")
    return "{}"
