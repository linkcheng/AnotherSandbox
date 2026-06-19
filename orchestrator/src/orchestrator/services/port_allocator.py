"""端口分配：查询已占用端口集，返回范围内最小可用端口。research.md R2, data-model.md §5.3。

并发兜底由 workspaces.external_port 的 partial unique index 保证（插入冲突时 caller 重试）。
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.config import get_settings


async def allocate_port(session: AsyncSession) -> int:
    s = get_settings()
    rows = await session.execute(
        text("SELECT external_port FROM workspaces WHERE deleted_at IS NULL")
    )
    used = set(rows.scalars().all())
    for port in range(s.workspace_port_start, s.workspace_port_end + 1):
        if port not in used:
            return port
    raise RuntimeError(
        f"no available workspace port in [{s.workspace_port_start},{s.workspace_port_end}]"
    )
