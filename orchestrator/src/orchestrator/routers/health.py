"""健康端点。contracts/orchestrator-rest-api.md §4。"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.db import get_session

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    """liveness：不查 DB，恒 200。"""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_session)) -> JSONResponse:
    """readiness：查 DB 连通。可达 200；不可达 503。"""
    try:
        await session.execute(text("SELECT 1"))
        return JSONResponse(status_code=200, content={"status": "ready", "db": "ok"})
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "db": "unavailable"})
