"""cap-terminal GET /api/v1/terminal/status 路由。

对应 spec.md FR-020；contracts/cap-terminal-api.md §3。
注：/api/v1/health 已在 routers/health.py 实现，此处不重复。
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter

from cap_terminal.tmux_session import tmux_session

router = APIRouter()


@router.get("/api/v1/terminal/status")
async def terminal_status() -> dict[str, Any]:
    """返回 tmux session 元信息（session_name/windows/panes/alive）。

    cap-agent /v1/shell/sessions 透传此端点。
    """
    return await asyncio.to_thread(tmux_session.status)
