"""T045: reaper 集成测试。research.md R1。"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from orchestrator.services.reaper import reap_expired

pytestmark = pytest.mark.integration


async def test_reap_deletes_only_expired(pg_url):
    engine = create_async_engine(pg_url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    async with maker() as session:
        await session.execute(text("INSERT INTO users (id,email,password_hash) VALUES (gen_random_uuid(),'r@b.c','h')"))
        uid = (await session.execute(text("SELECT id FROM users WHERE email='r@b.c'"))).scalar_one()
        # 过期 deleted（10 天前，> retention 7）
        await session.execute(text(
            "INSERT INTO workspaces (id,name,slug,owner_user_id,status,compose_project,external_port,volume_path,deleted_at) "
            "VALUES (gen_random_uuid(),'old','ws-old',:uid,'deleted','ws-old',9999,'/tmp/old',:t)"
        ), {"uid": uid, "t": now - timedelta(days=10)})
        # 未过期 deleted（1 天前，< retention 7）
        await session.execute(text(
            "INSERT INTO workspaces (id,name,slug,owner_user_id,status,compose_project,external_port,volume_path,deleted_at) "
            "VALUES (gen_random_uuid(),'recent','ws-recent',:uid,'deleted','ws-recent',9998,'/tmp/recent',:t)"
        ), {"uid": uid, "t": now - timedelta(days=1)})
        # 活跃（不删）
        await session.execute(text(
            "INSERT INTO workspaces (id,name,slug,owner_user_id,status,compose_project,external_port,volume_path) "
            "VALUES (gen_random_uuid(),'live','ws-live',:uid,'running','ws-live',9997,'/tmp/live')"
        ), {"uid": uid})
        await session.commit()

    async with maker() as session:
        n = await reap_expired(session, run_compose_down=False)
        assert n == 1  # 只删过期的

    # 验证 recent + live 仍在
    async with maker() as session:
        remaining = set((await session.execute(
            text("SELECT slug FROM workspaces WHERE deleted_at IS NOT NULL OR status != 'deleted'")
        )).scalars().all())
        assert "ws-recent" in remaining
        assert "ws-live" in remaining
        assert "ws-old" not in remaining
    await engine.dispose()
