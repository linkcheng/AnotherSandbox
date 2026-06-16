"""E2E 测试公共 fixture。

所有测试默认打 http://localhost:80（cap-nginx 反代）。
可通过 BASE_URL 环境变量切换（如 http://localhost:8080）。
"""
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
import httpx


@pytest.fixture(scope="session")
def base_url() -> str:
    """E2E 入口 URL。"""
    return os.getenv("E2E_BASE_URL", "http://localhost")


@pytest.fixture
def client(base_url: str) -> Iterator[httpx.Client]:
    """同步 HTTP 客户端（默认 10s 超时）。"""
    with httpx.Client(base_url=base_url, timeout=10.0) as c:
        yield c


@pytest.fixture
async def aclient(base_url: str) -> Iterator[httpx.AsyncClient]:
    """异步 HTTP 宯户端（用于 WebSocket 与长轮询）。"""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as c:
        yield c
