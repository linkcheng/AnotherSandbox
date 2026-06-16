"""cap-agent /cdp/* 路由：反代 cap-browser:9222 CDP endpoint。

- HTTP /cdp/json* 通过 browser_cdp_client
- WebSocket /cdp/devtools/{target_id} 双向桥接（用 websockets 库）
"""
from __future__ import annotations

import asyncio
from typing import Any

import websockets
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from cap_agent.services.browser_cdp_client import browser_cdp_client

router = APIRouter()


@router.get("/cdp/json")
async def cdp_json() -> list[dict[str, Any]]:
    """CDP target 列表（HTTP 透传）。"""
    try:
        return await browser_cdp_client.get_json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/cdp/json/version")
async def cdp_json_version() -> dict[str, Any]:
    """CDP 版本信息。"""
    try:
        return await browser_cdp_client.get_version()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/cdp/json/list")
async def cdp_json_list() -> list[dict[str, Any]]:
    """等价于 /cdp/json。"""
    return await cdp_json()


@router.websocket("/cdp/devtools/{target_id}")
async def cdp_devtools_ws(websocket: WebSocket, target_id: str) -> None:
    """双向桥接 WebSocket：client ↔ cap-browser:9222/devtools/{target_id}。

    上游不可达时关闭（code 1011）。
    """
    await websocket.accept()
    upstream_url = f"ws://cap-browser:9222/devtools/{target_id}"

    try:
        async with websockets.connect(upstream_url) as upstream:
            await _bridge(websocket, upstream)
    except Exception:
        # 上游不可达：通知客户端后关闭
        await websocket.close(code=1011)
        return


async def _bridge(client: WebSocket, upstream: Any) -> None:  # pragma: no cover
    """双向转发直到任一端断开。

    P1 仅占位实现；完整桥接逻辑与测试在 US5/Polish 阶段补齐
    （需启动真实 cap-browser Chromium）。
    """

    async def client_to_upstream() -> None:
        try:
            while True:
                data = await client.receive_text()
                await upstream.send(data)
        except WebSocketDisconnect:
            pass

    async def upstream_to_client() -> None:
        try:
            async for msg in upstream:
                await client.send_text(msg)
        except Exception:
            pass

    task_c2u = asyncio.create_task(client_to_upstream())
    task_u2c = asyncio.create_task(upstream_to_client())

    done, pending = await asyncio.wait(
        {task_c2u, task_u2c},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for t in pending:
        t.cancel()
