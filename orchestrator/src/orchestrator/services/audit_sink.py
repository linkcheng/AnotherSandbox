"""审计写入 + 校验。contracts/audit-ingest.md §2/3。"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models.audit_log import AuditLog

VALID_EVENT_TYPES = {"shell.exec", "fs.write", "browser.action", "gui.action"}
VALID_SOURCES = {"cap-terminal", "cap-mcp", "cap-agent"}


async def write_audit(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    event_type: str,
    source: str,
    detail: dict,
    success: bool,
) -> AuditLog:
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(f"invalid event_type: {event_type}")
    if source not in VALID_SOURCES:
        raise ValueError(f"invalid source: {source}")
    log = AuditLog(
        workspace_id=workspace_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        source=source,
        detail=detail,
        success=success,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log
