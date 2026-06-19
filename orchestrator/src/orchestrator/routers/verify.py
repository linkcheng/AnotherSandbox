"""auth_request 目标：校验 JWT + workspace 归属，回写可信 header。

被 workspace cap-nginx 的 auth_request 调用（不消费 body）。nginx 用 auth_request_set
捕获 X-User-Id/X-Workspace-Id/X-Permissions 透传给 cap-agent。contracts/trusted-headers.md。
"""
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.db import get_session
from orchestrator.core.security import decode_token
from orchestrator.models.workspace_owner import WorkspaceOwner

router = APIRouter(prefix="/api/v1", tags=["verify"])


@router.post("/verify")
async def verify(
    response: Response,
    authorization: str | None = Header(default=None),
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
    session: AsyncSession = Depends(get_session),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}}) from None
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail={"error": {"code": "bad_request", "message": "missing X-Workspace-Id"}})
    try:
        user_id = uuid.UUID(payload["sub"])
        ws_id = uuid.UUID(x_workspace_id)
    except (KeyError, ValueError):
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}}) from None
    wo = await session.scalar(
        select(WorkspaceOwner).where(
            WorkspaceOwner.workspace_id == ws_id, WorkspaceOwner.user_id == user_id
        )
    )
    if wo is None:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden"}})
    response.headers["X-User-Id"] = str(user_id)
    response.headers["X-Workspace-Id"] = str(ws_id)
    response.headers["X-Permissions"] = wo.role
    return {"ok": True}
