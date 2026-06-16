"""cap-agent /gui/* 路由：screenshot 与 actions。

pyautogui 唯一持有者为 cap-agent，通过共享 X display socket 访问
cap-browser 的 Xvnc。对应 spec.md FR-018、研究 R5。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter

from cap_agent.models.actions import GUIAction
from cap_agent.services.gui_backend import gui_backend

router = APIRouter()

_action_adapter = TypeAdapter(GUIAction)


@router.get("/gui/screenshot")
async def screenshot() -> StreamingResponse:
    """截取当前 X display，返回 PNG bytes。"""
    try:
        png = await gui_backend.screenshot()
    except Exception as e:  # noqa: BLE001 — 任何 pyautogui 失败统一转 500
        raise HTTPException(status_code=500, detail=f"screenshot failed: {e}") from e
    return StreamingResponse(
        iter([png]),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/gui/actions")
async def actions(action: dict[str, Any]) -> dict[str, Any]:
    """执行 16 种桌面动作之一（discriminated union by action_type）。"""
    try:
        parsed = _action_adapter.validate_python(action)
    except Exception as e:  # noqa: BLE001 — pydantic 校验失败统一转 422
        raise HTTPException(status_code=422, detail=f"invalid action: {e}") from e

    try:
        result = await gui_backend.execute(parsed)
    except Exception as e:  # noqa: BLE001 — backend 异常统一转 500
        raise HTTPException(status_code=500, detail=f"action failed: {e}") from e
    return result
