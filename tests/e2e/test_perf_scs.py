"""P1 性能验收测试（Success Criteria）。

对应 spec.md SC-001~SC-008；tasks.md T091。
前置：`make up` 已启动完整 stack。
"""
from __future__ import annotations

import json
import subprocess
import time
import uuid

import pytest
import httpx


SC_005_SHELL_LATENCY_MS = 500
SC_006_FS_CONSISTENCY_MS = 100


@pytest.mark.smoke
def test_sc_005_shell_exec_latency(client: httpx.Client) -> None:
    """SC-005: MCP shell_exec('echo hi') 端到端延迟 < 500ms。"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "shell_exec", "arguments": {"command": "echo hi"}},
    }
    start = time.monotonic()
    response = client.post("/mcp/sandbox/", json=payload, timeout=30)
    elapsed_ms = (time.monotonic() - start) * 1000

    assert response.status_code == 200
    assert elapsed_ms < SC_005_SHELL_LATENCY_MS, (
        f"shell_exec 端到端延迟 {elapsed_ms:.0f}ms 超过 {SC_005_SHELL_LATENCY_MS}ms"
    )


@pytest.mark.fs
def test_sc_006_fs_consistency(client: httpx.Client) -> None:
    """SC-006: fs_write 后 fs_read 内容一致，延迟 < 100ms。"""
    unique = uuid.uuid4().hex[:8]
    path = f"/workspace/shared/perf-{unique}.txt"
    content = f"perf-test-{unique}"

    write_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "fs_write",
            "arguments": {"path": path, "content": content},
        },
    }
    write_resp = client.post("/mcp/sandbox/", json=write_payload, timeout=10)
    assert write_resp.status_code == 200

    start = time.monotonic()
    read_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "fs_read", "arguments": {"path": path}},
    }
    read_resp = client.post("/mcp/sandbox/", json=read_payload, timeout=10)
    elapsed_ms = (time.monotonic() - start) * 1000

    assert read_resp.status_code == 200
    assert elapsed_ms < SC_006_FS_CONSISTENCY_MS, (
        f"fs_read 延迟 {elapsed_ms:.0f}ms 超过 {SC_006_FS_CONSISTENCY_MS}ms"
    )

    body = read_resp.json()
    text = _extract_text(body)
    data = json.loads(text)
    assert data.get("content") == content


@pytest.mark.smoke
def test_sc_007_total_memory_under_5gb() -> None:
    """SC-007: 7 cap-* 容器稳态总内存 < 5GB。"""
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"docker stats 失败: {result.stderr}"

    total_bytes = 0.0
    for line in result.stdout.strip().splitlines():
        used = line.split("/")[0].strip()
        total_bytes += _parse_size(used)

    total_gb = total_bytes / (1024 ** 3)
    assert total_gb < 5.0, f"7 容器总内存 {total_gb:.2f}GB 超过 5GB"


def _extract_text(mcp_response: dict) -> str:
    """从 MCP 标准响应提取 content[0].text。"""
    result = mcp_response.get("result", {})
    content = result.get("content", [])
    if content and isinstance(content, list):
        return content[0].get("text", "{}")
    return "{}"


def _parse_size(s: str) -> float:
    """'123.45MiB' → bytes（float）。"""
    s = s.strip()
    units = {"B": 1, "KiB": 1024, "MiB": 1024 ** 2, "GiB": 1024 ** 3, "TiB": 1024 ** 4}
    for unit, factor in sorted(units.items(), key=lambda x: -len(x[0])):
        if s.endswith(unit):
            try:
                return float(s[: -len(unit)].strip()) * factor
            except ValueError:
                return 0
    return 0
