"""cap-browser CDP endpoint HTTP 客户端。

注：WebSocket 反代在 routers/cdp.py 用 FastAPI WebSocket 直接处理（httpx 不支持 WS）。
"""
from __future__ import annotations

from typing import Any

import httpx

from cap_agent.core.config import settings
from cap_agent.core.exceptions import UpstreamError


class BrowserCDPClient:
    """cap-browser CDP HTTP API 客户端。"""

    def __init__(self, base_url: str | None = None) -> None:
        """初始化客户端。

        Args:
            base_url: cap-browser CDP 根 URL；默认读 settings.browser_cdp_url。
        """
        self._base_url = base_url or settings.browser_cdp_url

    async def get_json(self) -> list[dict[str, Any]]:
        """GET /json — 获取 CDP target 列表。"""
        return await self._get("/json")

    async def get_version(self) -> dict[str, Any]:
        """GET /json/version — 获取 Chromium 版本信息。"""
        return await self._get("/json/version")

    async def _get(self, path: str) -> Any:
        """统一 GET：网络/状态码错误转 UpstreamError。"""
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=5.0
            ) as client:
                response = await client.get(path)
        except (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
        ) as e:
            raise UpstreamError(f"cap-browser CDP 不可达: {e}") from e

        if response.status_code >= 400:
            raise UpstreamError(
                f"cap-browser CDP 返回 {response.status_code}: "
                f"{response.text[:200]}"
            )

        return response.json()


# 模块级单例
browser_cdp_client = BrowserCDPClient()
