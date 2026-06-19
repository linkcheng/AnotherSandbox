"""T047: Alembic 0003_workspace_error 迁移集成测试（testcontainers-postgres）。

验证：
  - 0002→0003 upgrade：workspaces 增 error_message（TEXT, nullable）
  - downgrade 幂等（upgrade→downgrade→upgrade 往返）
仿 test_migration_oauth.py 模式。无 Docker 跳过（不失败）。
"""
import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.integration

HAS_DOCKER = os.system("docker info >/dev/null 2>&1") == 0
skip_no_docker = pytest.mark.skipif(not HAS_DOCKER, reason="Docker 不可用（testcontainers 需要）")


def _cfg(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@skip_no_docker
def test_upgrade_0003_adds_error_message_column():
    """0003 upgrade 给 workspaces 增 error_message（TEXT, nullable）。"""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url().replace("localhost", "127.0.0.1")
        command.upgrade(_cfg(url), "head")

        async def verify() -> None:
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(url)
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            "SELECT data_type, is_nullable FROM information_schema.columns "
                            "WHERE table_name='workspaces' AND column_name='error_message'"
                        )
                    )
                ).one_or_none()
                assert row is not None, "error_message 列不存在"
                assert row[0] == "text"
                assert row[1] == "YES"  # nullable
            await engine.dispose()

        asyncio.run(verify())


@skip_no_docker
def test_migration_0003_upgrade_downgrade_upgrade_idempotent():
    """upgrade→downgrade→upgrade 往返幂等。"""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url().replace("localhost", "127.0.0.1")
        command.upgrade(_cfg(url), "head")
        # 降回 0002_oauth（撤销 error_message）
        command.downgrade(_cfg(url), "0002_oauth")
        # 再升到 head，不应报错
        command.upgrade(_cfg(url), "head")

        async def verify() -> None:
            from sqlalchemy.ext.asyncio import create_async_engine

            engine = create_async_engine(url)
            async with engine.connect() as conn:
                row = (
                    await conn.execute(
                        text(
                            "SELECT data_type FROM information_schema.columns "
                            "WHERE table_name='workspaces' AND column_name='error_message'"
                        )
                    )
                ).one_or_none()
                assert row is not None and row[0] == "text"
            await engine.dispose()

        asyncio.run(verify())
