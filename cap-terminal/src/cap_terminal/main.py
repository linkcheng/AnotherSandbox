"""cap-terminal FastAPI 应用装配。"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cap_terminal.routers import exec, health, status


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：US1 占位，US2 起将初始化 shell 会话池等资源。"""
    yield


def create_app() -> FastAPI:
    """构建 FastAPI 应用实例。"""
    app = FastAPI(
        title="cap-terminal",
        description="AI 个人沙箱 shell 共享服务",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(exec.router)
    app.include_router(status.router)
    return app


app = create_app()
