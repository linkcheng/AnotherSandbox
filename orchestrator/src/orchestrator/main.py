"""Orchestrator FastAPI app。plan.md M0。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from orchestrator.routers import health

logger = logging.getLogger("orchestrator")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alembic upgrade head 在 Phase 2 完整版（T018/T019 落地后）接入；
    # 当前 /healthz 可独立工作，/readyz 依赖外部 PostgreSQL。
    logger.info("Orchestrator lifespan: start")
    yield
    logger.info("Orchestrator lifespan: stop")


def create_app() -> FastAPI:
    app = FastAPI(title="Orchestrator", version="0.1.0", lifespan=lifespan)
    app.include_router(health.router)
    return app


app = create_app()
