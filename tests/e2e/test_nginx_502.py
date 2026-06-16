"""cap-nginx 上游不可用返回 502 测试。

对应 spec.md FR-014、US5 AC2；tasks.md T070。
前置：`make up` 已启动完整 stack。
"""
from __future__ import annotations

import subprocess
import time

import pytest
import httpx


@pytest.mark.smoke
def test_jupyter_unavailable_returns_502(client: httpx.Client) -> None:
    """停止 cap-jupyter 后 /jupyter/ 返回 502。"""
    # 停止 cap-jupyter
    subprocess.run(["docker", "compose", "stop", "cap-jupyter"], check=True)
    try:
        time.sleep(2)  # 等待 nginx 探测到上游不可用
        response = client.get("/jupyter/api/status", timeout=10)
        assert response.status_code in (502, 503), f"期望 502/503，实际 {response.status_code}"
    finally:
        # 恢复服务
        subprocess.run(["docker", "compose", "start", "cap-jupyter"], check=True)
        time.sleep(5)  # 等待 healthy
