"""cap-agent /gui/screenshot 端到端测试。

对应 spec.md FR-018 / FR-031；tasks.md T081。
前置：`make up` 已启动完整 stack。
"""
from __future__ import annotations

import pytest
import httpx


@pytest.mark.gui
def test_gui_screenshot_returns_png(client: httpx.Client) -> None:
    """GET /gui/screenshot 返回 image/png 大小 > 1KB。"""
    response = client.get("/gui/screenshot", timeout=30)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 1024
