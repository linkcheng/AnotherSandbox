"""cap-agent 健康检查路由。"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/v1/health")
async def health() -> dict[str, str]:
    """返回服务存活标记。

    Returns:
        {"status": "ok"} 表示服务可用。
    """
    return {"status": "ok"}
