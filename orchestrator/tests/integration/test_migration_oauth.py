"""T015: Alembic 0002_oauth 迁移集成测试（testcontainers-postgres）。

data-model.md §4。验证：
  - 0001→0002 upgrade：建 oauth_accounts 表（CHECK/UNIQUE/索引）+ users 增列
  - downgrade 幂等（upgrade→downgrade→upgrade 往返）
  - UNIQUE(provider, provider_user_id) 生效（防重复绑定）
  - CHECK provider IN (github, google) 生效
"""
import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

HAS_DOCKER = os.system("docker info >/dev/null 2>&1") == 0
skip_no_docker = pytest.mark.skipif(not HAS_DOCKER, reason="Docker 不可用（testcontainers 需要）")


def _cfg(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@skip_no_docker
def test_upgrade_0002_creates_oauth_table_and_user_columns():
    """0002_oauth upgrade 建 oauth_accounts 表 + users 增 display_name/avatar_url。"""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url().replace("localhost", "127.0.0.1")
        command.upgrade(_cfg(url), "head")

        async def verify() -> None:
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(url)
            async with engine.connect() as conn:
                # oauth_accounts 表存在
                tables = (
                    await conn.execute(
                        text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                    )
                ).scalars().all()
                assert "oauth_accounts" in tables

                # users 增列 display_name/avatar_url（nullable）
                cols = (
                    await conn.execute(
                        text(
                            "SELECT column_name, is_nullable FROM information_schema.columns "
                            "WHERE table_name='users' AND column_name IN ('display_name','avatar_url')"
                        )
                    )
                ).all()
                assert len(cols) == 2
                for _, nullable in cols:
                    assert nullable == "YES"

                # provider CHECK 约束存在
                checks = (
                    await conn.execute(
                        text(
                            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                            "WHERE conname='ck_oauth_provider'"
                        )
                    )
                ).scalar_one_or_none()
                assert checks is not None
                assert "github" in checks and "google" in checks

                # UNIQUE(provider, provider_user_id) 约束存在
                uniq = (
                    await conn.execute(
                        text(
                            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                            "WHERE conname='uq_oauth_provider_user'"
                        )
                    )
                ).scalar_one_or_none()
                assert uniq is not None
                assert "provider" in uniq and "provider_user_id" in uniq

            await engine.dispose()

        asyncio.run(verify())


@skip_no_docker
def test_migration_0002_upgrade_downgrade_upgrade_idempotent():
    """upgrade→downgrade→upgrade 往返幂等（data-model §4）。"""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url().replace("localhost", "127.0.0.1")
        command.upgrade(_cfg(url), "head")
        # 降回 0001_init（撤销 oauth_accounts + users 增列）
        command.downgrade(_cfg(url), "0001_init")
        # 再升到 head，不应报错
        command.upgrade(_cfg(url), "head")

        async def verify() -> None:
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(url)
            async with engine.connect() as conn:
                tables = (
                    await conn.execute(
                        text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                    )
                ).scalars().all()
                assert "oauth_accounts" in tables
            await engine.dispose()

        asyncio.run(verify())


@skip_no_docker
def test_oauth_unique_provider_user_id_enforced():
    """UNIQUE(provider, provider_user_id) 防重复绑定（R2）。"""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url().replace("localhost", "127.0.0.1")
        command.upgrade(_cfg(url), "head")

        async def verify() -> None:
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(url)
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO users (id,email,password_hash) VALUES (gen_random_uuid(),'a@b.c','h')")
                )
                uid = (await conn.execute(text("SELECT id FROM users WHERE email='a@b.c'"))).scalar_one()
                # 同 (provider, provider_user_id) 插两条 → 第二条违反 UNIQUE
                await conn.execute(
                    text(
                        "INSERT INTO oauth_accounts (provider, provider_user_id, user_id, email) "
                        "VALUES ('github', 'gh-001', :uid, 'a@b.c')"
                    ),
                    {"uid": uid},
                )
                with pytest.raises(IntegrityError):
                    await conn.execute(
                        text(
                            "INSERT INTO oauth_accounts (provider, provider_user_id, user_id, email) "
                            "VALUES ('github', 'gh-001', :uid, 'a@b.c')"
                        ),
                        {"uid": uid},
                    )
            await engine.dispose()

        asyncio.run(verify())


@skip_no_docker
def test_oauth_provider_check_constraint_rejects_unknown():
    """CHECK provider IN (github, google) 拒绝其他值。"""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url().replace("localhost", "127.0.0.1")
        command.upgrade(_cfg(url), "head")

        async def verify() -> None:
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(url)
            async with engine.begin() as conn:
                await conn.execute(
                    text("INSERT INTO users (id,email,password_hash) VALUES (gen_random_uuid(),'x@y.z','h')")
                )
                uid = (await conn.execute(text("SELECT id FROM users WHERE email='x@y.z'"))).scalar_one()
                with pytest.raises(IntegrityError):
                    await conn.execute(
                        text(
                            "INSERT INTO oauth_accounts (provider, provider_user_id, user_id) "
                            "VALUES ('facebook', 'fb-1', :uid)"
                        ),
                        {"uid": uid},
                    )
            await engine.dispose()

        asyncio.run(verify())
