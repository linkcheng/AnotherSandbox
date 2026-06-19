"""T036: port_allocator integration（generate_series 最小可用端口）。research.md R2。"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from orchestrator.core.config import get_settings
from orchestrator.services.port_allocator import allocate_port

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_allocate_returns_start_when_empty(pg_url):
    engine = create_async_engine(pg_url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    s = get_settings()
    async with maker() as session:
        port = await allocate_port(session)
        assert port == s.workspace_port_start  # 空表 → 最小端口
    await engine.dispose()


@pytest.mark.asyncio
async def test_allocate_skips_occupied_ports(pg_url):
    engine = create_async_engine(pg_url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    s = get_settings()
    async with maker() as session:
        # 建一个 user + 占用 START 端口的活跃 workspace
        await session.execute(text("INSERT INTO users (id,email,password_hash) VALUES (gen_random_uuid(),'p@b.c','h')"))
        uid = (await session.execute(text("SELECT id FROM users WHERE email='p@b.c'"))).scalar_one()
        await session.execute(text(
            "INSERT INTO workspaces (id,name,slug,owner_user_id,status,compose_project,external_port,volume_path) "
            "VALUES (gen_random_uuid(),'w','w',:uid,'stopped','w',:port,'/tmp/w')"
        ), {"uid": uid, "port": s.workspace_port_start})
        await session.commit()
        # 再次分配应跳过 START，返回 START+1
        port = await allocate_port(session)
        assert port == s.workspace_port_start + 1
    await engine.dispose()
