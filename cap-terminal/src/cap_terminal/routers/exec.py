"""cap-terminal POST /api/v1/exec 路由。

对应 spec.md FR-020、FR-021；contracts/cap-terminal-api.md §2。
P2：执行后 fire-and-forget 上报 shell.exec 审计（contracts/audit-ingest.md）。
"""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from cap_terminal.services.audit_client import audit_client
from cap_terminal.tmux_session import tmux_session

router = APIRouter()


class ExecRequest(BaseModel):
    command: Annotated[str, Field(min_length=1, description="要执行的 shell 命令")]
    timeout_s: int = Field(default=30, ge=1, le=600, description="超时秒数")


class ExecResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@router.post("/api/v1/exec", response_model=ExecResponse)
async def exec_command(req: ExecRequest, request: Request) -> ExecResponse:
    """在共享 tmux session 中执行命令。"""
    result = await asyncio.to_thread(
        tmux_session.run,
        req.command,
        timeout_s=req.timeout_s,
    )
    # P2 审计：fire-and-forget（未配置则静默跳过，绝不阻塞业务）
    audit_client.report(
        "shell.exec",
        {"command": req.command, "exit_code": result["exit_code"], "duration_ms": result["duration_ms"]},
        actor_user_id=request.headers.get("X-User-Id"),
        success=result["exit_code"] == 0,
    )
    return ExecResponse(**result)
