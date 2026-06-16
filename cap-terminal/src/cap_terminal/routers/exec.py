"""cap-terminal POST /api/v1/exec 路由。

对应 spec.md FR-020、FR-021；contracts/cap-terminal-api.md §2。
"""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter
from pydantic import BaseModel, Field

from cap_terminal.tmux_session import tmux_session

router = APIRouter()


class ExecRequest(BaseModel):
    """shell 执行请求。"""

    command: Annotated[
        str, Field(min_length=1, description="要执行的 shell 命令")
    ]
    timeout_s: int = Field(default=30, ge=1, le=600, description="超时秒数")


class ExecResponse(BaseModel):
    """shell 执行响应。"""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@router.post("/api/v1/exec", response_model=ExecResponse)
async def exec_command(req: ExecRequest) -> ExecResponse:
    """在共享 tmux session 中执行命令。

    命令在固定 window 内同步执行，human 通过 ttyd 可见相同输出（共享语义）。
    libtmux 是同步阻塞 API，用 asyncio.to_thread 避免阻塞 event loop。
    """
    result = await asyncio.to_thread(
        tmux_session.run,
        req.command,
        timeout_s=req.timeout_s,
    )
    return ExecResponse(**result)
