"""cap-agent pytest fixtures。"""
from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    """加载 FastAPI app 并返回 TestClient。"""
    # 健康测试不需要下游服务，禁用真实连接
    os.environ.setdefault("TERMINAL_URL", "http://cap-terminal:7682")
    os.environ.setdefault("BROWSER_CDP_URL", "http://cap-browser:9222")

    from cap_agent.main import app

    with TestClient(app) as test_client:
        yield test_client
