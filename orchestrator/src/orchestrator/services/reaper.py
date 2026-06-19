"""软删除超期 workspace 硬删（R1）。data-model §6, research.md R1。

由 Orchestrator lifespan 周期调度（reap_expired）；retention=0 时立即硬删（CI 用）。
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.config import get_settings
from orchestrator.models.workspace import Workspace
from orchestrator.services import compose_runner


async def reap_expired(session: AsyncSession, *, run_compose_down: bool = True) -> int:
    """删除 deleted_at + retention < now 的 workspace（硬删）。返回删除数。

    run_compose_down=False 供测试跳过真实 compose（仅删 DB 行）。
    """
    s = get_settings()
    now = datetime.now(timezone.utc)
    threshold = now if s.workspace_retention_days == 0 else now - timedelta(days=s.workspace_retention_days)
    rows = await session.execute(
        select(Workspace).where(Workspace.deleted_at.is_not(None), Workspace.deleted_at < threshold)
    )
    expired = rows.scalars().all()
    for ws in expired:
        if run_compose_down:
            env = compose_runner.workspace_env(
                ws.slug, ws.external_port, ws.id, ws.volume_path,
                s.orch_url, "orchestrator", s.auth_failure_mode,
            )
            await compose_runner.down(ws.slug, env, s.workspace_compose_cwd, volumes=True)
        await session.delete(ws)
    if expired:
        await session.commit()
    return len(expired)
