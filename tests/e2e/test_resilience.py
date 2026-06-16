"""P1 韧性测试：服务崩溃后自动恢复。

对应 spec.md SC-008、edge cases；tasks.md T093。
前置：`make up` 已启动完整 stack。
"""
from __future__ import annotations

import json
import subprocess
import time

import pytest
import httpx


SC_008_RECOVERY_SEC = 10


@pytest.mark.browser
def test_sc_008_browser_restart_recovery(client: httpx.Client) -> None:
    """SC-008: cap-browser 崩溃重启后，cap-mcp browser 工具自动恢复 < 10s。"""
    subprocess.run(["docker", "compose", "restart", "cap-browser"], check=True, timeout=60)

    deadline = time.monotonic() + SC_008_RECOVERY_SEC
    last_error: str | None = None

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "browser_navigate",
            "arguments": {"url": "about:blank"},
        },
    }

    while time.monotonic() < deadline:
        try:
            response = client.post("/mcp/sandbox/", json=payload, timeout=5)
            if response.status_code == 200:
                body = response.json()
                if "result" in body or "content" in body:
                    return
            last_error = f"status={response.status_code}"
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            last_error = str(e)
        time.sleep(0.5)

    pytest.fail(f"cap-browser 重启后 {SC_008_RECOVERY_SEC}s 内未恢复: {last_error}")


@pytest.mark.smoke
def test_terminal_restart_keeps_workspace(client: httpx.Client) -> None:
    """cap-terminal 重启后 workspace 状态仍可读（bind mount 持久化）。"""
    write_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "fs_write",
            "arguments": {
                "path": "/workspace/shared/resilience-marker.txt",
                "content": "before-restart",
            },
        },
    }
    write_resp = client.post("/mcp/sandbox/", json=write_payload, timeout=10)
    assert write_resp.status_code == 200

    subprocess.run(["docker", "compose", "restart", "cap-terminal"], check=True, timeout=60)
    time.sleep(3)

    read_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "fs_read",
            "arguments": {"path": "/workspace/shared/resilience-marker.txt"},
        },
    }
    read_resp = client.post("/mcp/sandbox/", json=read_payload, timeout=10)
    assert read_resp.status_code == 200

    body = read_resp.json()
    result = body.get("result", {})
    content = result.get("content", [])
    if content:
        text = content[0].get("text", "{}")
        data = json.loads(text)
        assert data.get("content") == "before-restart"
