"""Integration 测试 fixtures：testcontainers-postgres + get_session dependency override。

策略：session 级复用 1 个 PG（alembic upgrade 一次），function 级 client 用同 PG
但 override get_session 指向该 engine；test 用唯一 email 避免数据冲突。
"""
import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

from orchestrator.core.db import get_session
from orchestrator.main import app

HAS_DOCKER = os.system("docker info >/dev/null 2>&1") == 0


@pytest.fixture(scope="session")
def pg_url():
    if not HAS_DOCKER:
        pytest.skip("Docker 不可用（testcontainers 需要）", allow_module_level=False)
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16", driver="asyncpg") as pg:
        url = pg.get_connection_url().replace("localhost", "127.0.0.1")
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        yield url


@pytest.fixture
def client(pg_url):
    engine = create_async_engine(pg_url)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_session():
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _override_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())
