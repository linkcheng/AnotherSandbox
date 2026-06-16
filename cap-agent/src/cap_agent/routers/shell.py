"""cap-agent /v1/shell/exec 路由。

转发到 cap-terminal:7682/api/v1/exec，保留共享语义。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from cap_agent.core.exceptions import UpstreamError
from cap_agent.services.terminal_client import terminal_client

router = APIRouter()


class ShellExecRequest(BaseModel):
    """shell 执行请求（与 cap-terminal 契约一致）。"""

    command: Annotated[str, Field(min_length=1)]
    timeout_s: int = Field(default=30, ge=1, le=600)


class ShellExecResponse(BaseModel):
    """shell 执行响应（透传 cap-terminal）。"""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@router.post("/v1/shell/exec", response_model=ShellExecResponse)
async def shell_exec(req: ShellExecRequest) -> ShellExecResponse:
    """转发 shell 命令到 cap-terminal。"""
    try:
        result = await terminal_client.exec(req.command, req.timeout_s)
    except UpstreamError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return ShellExecResponse(**result)
