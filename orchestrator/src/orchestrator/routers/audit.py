"""审计路由：ingest（workspace 内 cap-* 调用）+ query（需归属）。contracts/orchestrator-rest-api §3。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.db import get_session
from orchestrator.deps import get_current_user
from orchestrator.models.audit_log import AuditLog
from orchestrator.models.user import User
from orchestrator.models.workspace_owner import WorkspaceOwner
from orchestrator.schemas.audit import AuditIngestIn, AuditOut
from orchestrator.services.audit_sink import write_audit

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.post("/ingest", response_model=AuditOut, status_code=201)
async def ingest(body: AuditIngestIn, session: AsyncSession = Depends(get_session)):
    # 来自 workspace 内受信 cap-*（sandbox-net 隔离），无需 JWT
    try:
        return await write_audit(
            session,
            workspace_id=body.workspace_id, actor_user_id=body.actor_user_id,
            event_type=body.event_type, source=body.source,
            detail=body.detail, success=body.success,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": {"code": "bad_request", "message": str(e)}}) from None


@router.get("", response_model=list[AuditOut])
async def query_audit(
    workspace_id: uuid.UUID = Query(...),
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wo = await session.scalar(
        select(WorkspaceOwner).where(
            WorkspaceOwner.workspace_id == workspace_id, WorkspaceOwner.user_id == user.id
        )
    )
    if wo is None:
        raise HTTPException(status_code=403, detail={"error": {"code": "forbidden"}})
    q = select(AuditLog).where(AuditLog.workspace_id == workspace_id)
    if event_type:
        q = q.where(AuditLog.event_type == event_type)
    q = q.order_by(AuditLog.created_at.desc()).limit(limit)
    return (await session.execute(q)).scalars().all()
