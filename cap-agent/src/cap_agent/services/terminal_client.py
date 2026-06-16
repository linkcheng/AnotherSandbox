"""cap-terminal HTTP 客户端。

向 cap-terminal:7682 转发 shell 执行请求。
"""
from __future__ import annotations

from typing import Any

import httpx

from cap_agent.core.config import settings
from cap_agent.core.exceptions import UpstreamError


class TerminalClient:
    """cap-terminal HTTP 调用封装。"""

    def __init__(self, base_url: str | None = None) -> None:
        """初始化客户端。

        Args:
            base_url: cap-terminal 根 URL；默认读 settings.terminal_url。
        """
        self._base_url = base_url or settings.terminal_url

    async def exec(
        self,
        command: str,
        timeout_s: int = 30,
    ) -> dict[str, Any]:
        """POST /api/v1/exec 执行 shell 命令。

        Args:
            command: shell 命令。
            timeout_s: 超时秒数。

        Returns:
            {exit_code, stdout, stderr, duration_ms}。

        Raises:
            UpstreamError: cap-terminal 不可达或返回非 2xx。
        """
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=timeout_s + 5,  # 略大于命令超时
            ) as client:
                response = await client.post(
                    "/api/v1/exec",
                    json={"command": command, "timeout_s": timeout_s},
                )
        except (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
        ) as e:
            raise UpstreamError(f"cap-terminal 不可达: {e}") from e

        if response.status_code >= 400:
            raise UpstreamError(
                f"cap-terminal 返回 {response.status_code}: "
                f"{response.text[:200]}"
            )

        return response.json()


# 模块级单例
terminal_client = TerminalClient()
