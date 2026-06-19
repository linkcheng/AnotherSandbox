"""FastAPI 依赖：get_current_user（JWT→User）+ require_workspace_owner（归属校验）。"""
import uuid

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.db import get_session
from orchestrator.core.security import decode_token
from orchestrator.models.user import User
from orchestrator.models.workspace import Workspace
from orchestrator.models.workspace_owner import WorkspaceOwner

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not token:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    user = await session.get(User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"error": {"code": "unauthorized"}})
    return user


async def require_workspace_owner(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[Workspace, str]:
    """校验 workspace 存在 + 当前用户归属；返回 (workspace, role)。无归属 403。"""
    ws = await session.get(Workspace, workspace_id)
    if ws is None or ws.deleted_at is not None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found"}})
    wo = await session.scalar(
        select(WorkspaceOwner).where(
            WorkspaceOwner.workspace_id == workspace_id, WorkspaceOwner.user_id == user.id
        )
    )
    if wo is None:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden"}})
    return ws, wo.role
