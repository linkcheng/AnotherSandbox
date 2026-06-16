"""cap-terminal 健康检查路由。

注：US1 阶段占位实现；US2 将扩展为完整 shell-exec-api。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/v1/health")
async def health() -> dict[str, str]:
    """返回服务存活标记。

    Returns:
        {"status": "ok"} 表示服务可用。
    """
    return {"status": "ok"}
