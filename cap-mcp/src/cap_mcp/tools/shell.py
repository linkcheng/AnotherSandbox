"""cap-mcp shell_exec 工具：转发到 cap-agent:9000/v1/shell/exec。"""
from __future__ import annotations

import os
from typing import Any

import httpx

# 从环境变量读 cap-agent URL（容器内 DNS 默认值）
AGENT_URL = os.getenv("CAP_MCP_AGENT_URL", "http://cap-agent:9000")


async def shell_exec(command: str, timeout_s: int = 30) -> dict[str, Any]:
    """执行 shell 命令，返回结构化结果。

    转发到 cap-agent:9000/v1/shell/exec，后者再转发到 cap-terminal:7682。
    命令在共享 tmux session 中执行，human 通过 ttyd 可见相同输出。

    Args:
        command: 要执行的 shell 命令。
        timeout_s: 超时秒数，默认 30。

    Returns:
        {exit_code, stdout, stderr, duration_ms}；失败时 exit_code=-1
        且 stderr 含错误描述（不抛异常，让 MCP 客户端处理）。
    """
    try:
        async with httpx.AsyncClient(
            base_url=AGENT_URL,
            timeout=timeout_s + 5,
        ) as client:
            response = await client.post(
                "/v1/shell/exec",
                json={"command": command, "timeout_s": timeout_s},
            )
    except (
        httpx.ConnectError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
    ) as e:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"cap-agent unavailable: {e}",
            "duration_ms": 0,
        }

    if response.status_code >= 400:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"cap-agent error {response.status_code}",
            "duration_ms": 0,
        }

    return response.json()
