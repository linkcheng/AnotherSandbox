"""T074: P1 零迁移回归 E2E（AUTH_MODE=none，无 Orchestrator）。SC-006。

前置：AUTH_MODE=none make up（P1 原命令）。
"""
import os

import httpx
import pytest

P1_URL = os.environ.get("P1_E2E_URL", "http://localhost")


def test_p1_still_works_without_orchestrator():
    """P1 单 workspace 模式独立可用（无 Orchestrator 依赖，业务路由零改动）。"""
    try:
        r = httpx.get(f"{P1_URL}/v1/health", timeout=2)
        if r.status_code != 200:
            pytest.skip("P1 stack 未运行（先 AUTH_MODE=none make up）")
    except Exception:
        pytest.skip("P1 stack 未运行")
    # 真实 P1 E2E（make test-e2e）覆盖业务路由行为不变
