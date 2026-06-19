"""T058: P1 / P2 零迁移回归 E2E（SC-008 / FR-025/026/027/032）。

覆盖：
  - P1 单 workspace（AUTH_MODE=none）仍独立可用（无 orchestrator 依赖）。
  - P2 orchestrator 编排/认证/审计在 0002_oauth 迁移后回归（本地账户 Bearer 鉴权链路完整）。
前置：P1 stack（AUTH_MODE=none make up）+ P2 stack（make up-orchestrator）。
任一不可达自动 skip（不阻塞 CI/unit）。
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest

P1_URL = os.environ.get("P1_E2E_URL", "http://localhost")
ORCH = os.environ.get("ORCH_E2E_URL", "http://localhost:8000")


def test_p1_standalone_without_orchestrator():
    """P1：AUTH_MODE=none 单 workspace 独立可用（业务路由零改动，SC-008）。"""
    try:
        r = httpx.get(f"{P1_URL}/v1/health", timeout=2)
        if r.status_code != 200:
            pytest.skip("P1 stack 未运行（先 AUTH_MODE=none make up）")
    except Exception:
        pytest.skip("P1 stack 未运行")
    assert r.json() == {"status": "ok"}


def test_p2_local_auth_still_works_after_oauth_migration():
    """P2：0002_oauth 迁移后本地账户 Bearer 鉴权链路完整（零迁移核心断言）。

    FR-026 迁移幂等；FR-027 P2 既有端点不变；SC-008 P1/P2 回归全绿。
    """
    try:
        httpx.get(f"{ORCH}/healthz", timeout=2).raise_for_status()
    except Exception:
        pytest.skip("P2 orchestrator 未运行（先 make up-orchestrator）")

    email = f"reg-{uuid.uuid4().hex[:6]}@x.c"
    assert httpx.post(
        f"{ORCH}/api/v1/auth/register",
        json={"email": email, "password": "pw123456"},
    ).status_code == 201

    tok = httpx.post(
        f"{ORCH}/api/v1/auth/login",
        json={"email": email, "password": "pw123456"},
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    # /me + workspace CRUD（P2 既有链路）
    assert httpx.get(f"{ORCH}/api/v1/me", headers=h).status_code == 200
    ws = httpx.post(
        f"{ORCH}/api/v1/workspaces", json={"name": "reg"}, headers=h,
    ).json()
    assert ws["status"] == "created"
    assert httpx.get(f"{ORCH}/api/v1/workspaces", headers=h).status_code == 200
    # 审计端点可达
    assert httpx.get(
        f"{ORCH}/api/v1/audit", params={"workspace": ws["id"], "limit": 5}, headers=h,
    ).status_code == 200


def test_p2_verify_endpoint_reachable():
    """P2：/api/v1/verify（auth_request 目标）可达（workspace cap-nginx 依赖）。FR-023。"""
    try:
        httpx.get(f"{ORCH}/healthz", timeout=2).raise_for_status()
    except Exception:
        pytest.skip("P2 orchestrator 未运行")
    # 未带 token → 401/403/422（fail-closed，不穿透）
    r = httpx.get(f"{ORCH}/api/v1/verify", params={"workspace": "any"}, timeout=3)
    assert r.status_code in (401, 403, 422)
