"""cap-agent FastAPI 应用装配。"""
from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from cap_agent.routers import cdp, gui, health, shell


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动时注册 service，关闭时清理。"""
    # P1 阶段 health 端点不需要外部依赖
    yield


def create_app() -> FastAPI:
    """构建 FastAPI 应用实例。"""
    app = FastAPI(
        title="cap-agent",
        description="AI 个人沙箱业务编排服务",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(shell.router)
    app.include_router(cdp.router)
    app.include_router(gui.router)
    return app


app = create_app()
