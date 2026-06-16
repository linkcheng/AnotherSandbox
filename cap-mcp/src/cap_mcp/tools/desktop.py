"""cap-mcp desktop_* 工具：转发到 cap-agent:9000/gui/*。

pyautogui 唯一持有者为 cap-agent；cap-mcp 通过 HTTP 调用，
不直接 import pyautogui（避免 DISPLAY 依赖）。对应 spec.md FR-028。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

AGENT_URL = os.getenv("CAP_MCP_AGENT_URL", "http://cap-agent:9000")


def _default_workspace_root() -> str:
    """运行时读环境变量，便于测试 monkeypatch。"""
    return os.getenv("CAP_MCP_WORKSPACE_ROOT", "/workspace")


async def desktop_screenshot(path: str | None = None) -> dict[str, Any]:
    """截屏，保存到指定路径（默认 /workspace/shared/desktop.png）。

    转发到 cap-agent:9000/gui/screenshot，返回 PNG bytes 写入文件。
    """
    save_path = path or f"{_default_workspace_root()}/shared/desktop.png"
    try:
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=30.0) as client:
            response = await client.get("/gui/screenshot")
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
        return {"ok": False, "path": save_path, "bytes": 0, "error": f"cap-agent unavailable: {e}"}

    if response.status_code >= 400:
        return {"ok": False, "path": save_path, "bytes": 0, "error": f"cap-agent error {response.status_code}"}

    data = response.content
    Path(save_path).parent.mkdir(parents=True, exist_ok=True)
    Path(save_path).write_bytes(data)
    return {"ok": True, "path": save_path, "bytes": len(data)}


async def desktop_click(x: int, y: int, button: str = "left") -> dict[str, Any]:
    """点击坐标。

    Args:
        x: 横坐标。
        y: 纵坐标。
        button: left/right/middle，默认 left。
    """
    return await _post_action({"action_type": "click", "x": x, "y": y, "button": button})


async def desktop_type(text: str) -> dict[str, Any]:
    """输入文本（经 cap-agent 调 pyautogui）。"""
    return await _post_action({"action_type": "typing", "text": text})


async def _post_action(payload: dict[str, Any]) -> dict[str, Any]:
    """通用 action 转发。"""
    try:
        async with httpx.AsyncClient(base_url=AGENT_URL, timeout=15.0) as client:
            response = await client.post("/gui/actions", json=payload)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
        return {"ok": False, "error": f"cap-agent unavailable: {e}"}

    if response.status_code >= 400:
        return {"ok": False, "error": f"cap-agent error {response.status_code}"}

    return response.json()
