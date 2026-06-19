"""Alembic env：async engine + Base.metadata。research.md R6。

URL 解析：仅当 alembic.ini 仍是默认占位 url 时用应用 Settings.database_url；
调用方（testcontainers / 生产命令）显式 set_main_option 的 url 优先。
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from orchestrator.core.config import get_settings
# 导入所有模型，确保注册到 Base.metadata
from orchestrator.models import Base  # noqa: F401

DEFAULT_INI_URL = "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator"

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if config.get_main_option("sqlalchemy.url") == DEFAULT_INI_URL:
    config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
