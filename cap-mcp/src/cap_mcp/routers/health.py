"""cap-mcp 健康检查路由。

注：US1 阶段占位实现；US2/US3 将扩展为 MCP server。
路径为 /health（与 docker-compose healthcheck 对齐）。
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """返回服务存活标记。

    Returns:
        {"status": "ok"} 表示服务可用。
    """
    return {"status": "ok"}
