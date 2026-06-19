"""T073: 多 workspace 隔离 E2E（需完整 stack，≥3 workspace）。SC-005。"""
import os
import httpx
import pytest

ORCH = os.environ.get("ORCH_E2E_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def orch_up():
    try:
        httpx.get(f"{ORCH}/healthz", timeout=2).raise_for_status()
    except Exception:
        pytest.skip("Orchestrator + workspace stack 未运行")
    return ORCH


def test_three_workspaces_isolated(orch_up):
    """3 workspace 并发：独立 compose project/网络/卷（SC-005）。

    完整断言需 workspace 真实 start（shell 验证文件/网络隔离），
    在具备 P1 镜像 + Docker 的环境跑。
    """
    pytest.skip("需完整 workspace stack（P1 镜像 + 真实 compose start）验证隔离")
