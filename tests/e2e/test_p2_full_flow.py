"""T072: P2 完整流程 E2E（需 make up-orchestrator）。SC-001/002/007。

前置：make up-orchestrator（Orchestrator + PostgreSQL 运行）。
未运行时自动 skip（不阻塞 CI/unit）。
"""
import os

import httpx
import pytest

ORCH = os.environ.get("ORCH_E2E_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def orch_up():
    try:
        httpx.get(f"{ORCH}/healthz", timeout=2).raise_for_status()
    except Exception:
        pytest.skip("Orchestrator 未运行（先 make up-orchestrator）")
    return ORCH


def test_register_login_create_list(orch_up):
    """认证 + workspace 元数据闭环（SC-002/007）。"""
    import uuid
    email = f"e2e-{uuid.uuid4().hex[:6]}@x.c"
    assert httpx.post(f"{orch_up}/api/v1/auth/register",
                      json={"email": email, "password": "pw"}).status_code == 201
    tok = httpx.post(f"{orch_up}/api/v1/auth/login",
                     json={"email": email, "password": "pw"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    ws = httpx.post(f"{orch_up}/api/v1/workspaces", json={"name": "e2e"}, headers=h).json()
    assert ws["status"] == "created"
    assert httpx.get(f"{orch_up}/api/v1/workspaces", headers=h).status_code == 200
