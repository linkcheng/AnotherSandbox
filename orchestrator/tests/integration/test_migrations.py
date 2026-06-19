"""T020: Alembic 迁移集成测试（testcontainers-postgres）。data-model.md §4.3, research.md R6。

注：用 sync def test（alembic env.py 内部 asyncio.run 在 sync 上下文可正常调用）；
    DB 验证用独立 asyncio.run(verify()) 避免 event loop 冲突。
"""
import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration

HAS_DOCKER = os.system("docker info >/dev/null 2>&1") == 0
skip_no_docker = pytest.mark.skipif(not HAS_DOCKER, reason="Docker 不可用（testcontainers 需要）")


def _cfg(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@skip_no_docker
def test_upgrade_head_creates_tables_and_seed():
    """upgrade head 建全部 6 表 + minimal 种子；downgrade→upgrade 往返幂等。"""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url().replace("localhost","127.0.0.1")
        command.upgrade(_cfg(url), "head")

        async def verify() -> None:
            engine = create_async_engine(url)
            async with engine.connect() as conn:
                tables = (
                    await conn.execute(
                        text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
                    )
                ).scalars().all()
                assert set(tables) >= {
                    "users", "templates", "workspaces", "workspace_owners",
                    "refresh_tokens", "audit_logs",
                }
                minimal = (
                    await conn.execute(text("SELECT name FROM templates WHERE name='minimal'"))
                ).scalar_one_or_none()
                assert minimal == "minimal"
            await engine.dispose()

        asyncio.run(verify())

        command.downgrade(_cfg(url), "base")
        command.upgrade(_cfg(url), "head")


@skip_no_docker
def test_partial_unique_external_port():
    """partial unique index：活跃 ws 同 port 冲突；已删除 ws 同 port 允许。"""
    import sqlalchemy.exc
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url().replace("localhost","127.0.0.1")
        command.upgrade(_cfg(url), "head")

        async def verify() -> None:
            engine = create_async_engine(url)
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO users (id,email,password_hash) VALUES (gen_random_uuid(),'a@b.c','h')")
                )
                uid = (await conn.execute(text("SELECT id FROM users WHERE email='a@b.c'"))).scalar_one()
                await conn.execute(
                    text(
                        "INSERT INTO workspaces (id,name,slug,owner_user_id,status,compose_project,external_port,volume_path) "
                        "VALUES (gen_random_uuid(),'w1','w1',:uid,'stopped','w1',8101,'/tmp/w1')"
                    ),
                    {"uid": uid},
                )
                # 已删除 ws 同 port（deleted_at 非空）→ 允许
                await conn.execute(
                    text(
                        "INSERT INTO workspaces (id,name,slug,owner_user_id,status,compose_project,external_port,volume_path,deleted_at) "
                        "VALUES (gen_random_uuid(),'w2','w2',:uid,'deleted','w2',8101,'/tmp/w2',now())"
                    ),
                    {"uid": uid},
                )
            # 第二条活跃同 port → 唯一冲突
            async with engine.begin() as conn:
                with pytest.raises(sqlalchemy.exc.IntegrityError):
                    await conn.execute(
                        text(
                            "INSERT INTO workspaces (id,name,slug,owner_user_id,status,compose_project,external_port,volume_path) "
                            "VALUES (gen_random_uuid(),'w3','w3',:uid,'stopped','w3',8101,'/tmp/w3')"
                        ),
                        {"uid": uid},
                    )
            await engine.dispose()

        asyncio.run(verify())
