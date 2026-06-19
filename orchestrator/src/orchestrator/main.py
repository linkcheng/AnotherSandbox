"""Orchestrator FastAPI app。plan.md M0。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orchestrator.routers import auth, health

logger = logging.getLogger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 生产迁移由 Dockerfile CMD（alembic upgrade head && uvicorn）fail-fast 负责；
    # lifespan 仅日志，避免本地/测试启动强制依赖 DB。
    logger.info("Orchestrator lifespan: start")
    yield
    logger.info("Orchestrator lifespan: stop")


def create_app() -> FastAPI:
    app = FastAPI(title="Orchestrator", version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(auth.router)
    return app


app = create_app()
