"""cap-agent FastAPI 应用装配。"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cap_agent.core.auth import build_auth_middleware
from cap_agent.core.config import settings
from cap_agent.routers import cdp, gui, health, shell


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：启动时注册 service，关闭时清理。"""
    yield


def create_app() -> FastAPI:
    """构建 FastAPI 应用实例。按 AUTH_MODE 注册认证中间件（业务路由零改动）。"""
    app = FastAPI(
        title="cap-agent",
        description="AI 个人沙箱业务编排服务",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(build_auth_middleware(settings.auth_mode))
    app.include_router(health.router)
    app.include_router(shell.router)
    app.include_router(cdp.router)
    app.include_router(gui.router)
    return app


app = create_app()
