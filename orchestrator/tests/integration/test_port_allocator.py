"""T036: port_allocator integration。research.md R2, data-model.md §5.3。

注：session PG 复用，ws 跨 test 累积 → 不假设空表/固定端口，断言"未占用 + 在范围"。
"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from orchestrator.core.config import Settings, get_settings
from orchestrator.services import port_allocator
from orchestrator.services.port_allocator import allocate_port

pytestmark = pytest.mark.integration


async def _used_ports(pg_url: str) -> set[int]:
    engine = create_async_engine(pg_url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        used = set((await session.execute(
            text("SELECT external_port FROM workspaces WHERE deleted_at IS NULL")
        )).scalars().all())
    await engine.dispose()
    return used


@pytest.mark.asyncio
async def test_allocate_returns_unused_port_in_range(pg_url):
    used = await _used_ports(pg_url)
    engine = create_async_engine(pg_url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    s = get_settings()
    async with maker() as session:
        port = await allocate_port(session)
        assert port not in used  # 未被占用
        assert s.workspace_port_start <= port <= s.workspace_port_end
    await engine.dispose()


@pytest.mark.asyncio
async def test_allocate_raises_when_range_exhausted(pg_url, monkeypatch):
    # 范围置空（START > END）→ 循环不执行 → RuntimeError
    fake = Settings(workspace_port_start=9000, workspace_port_end=8999)
    monkeypatch.setattr(port_allocator, "get_settings", lambda: fake)
    engine = create_async_engine(pg_url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        with pytest.raises(RuntimeError):
            await allocate_port(session)
    await engine.dispose()
