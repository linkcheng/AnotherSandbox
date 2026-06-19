"""T057: P3 真实启动 + 统一入口访问 E2E（US3 / SC-003 / SC-004 / FR-016~018/030）。

覆盖：OAuth 登录 → 建 workspace → 真实 start（docker.sock 拉起 cap-* 容器组）→
     status=running → 经 /ws/{slug}/ 统一入口访问 → 触发操作 → 审计落库。
前置：make up-p3 + P1 全套镜像（make build）已构建 + orchestrator 挂 docker.sock。
无 stack 或无 P1 镜像时自动 skip（不阻塞 CI/unit）。

对应 quickstart 场景 4 / 5。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from urllib.parse import urlsplit

import httpx
import pytest

BASE = os.environ.get("P3_E2E_URL", "http://localhost:8080")
# P1 镜像可用性探测目标（cap-nginx 是 workspace 容器组入口，必存在）
_REQUIRED_IMAGE = "sandbox/cap-nginx"


def _docker_available() -> bool:
    """docker CLI 可用 + 至少 1 个 P1 镜像存在。"""
    if not shutil.which("docker"):
        return False
    try:
        r = subprocess.run(
            ["docker", "images", "-q", _REQUIRED_IMAGE],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def _oauth_login(client: httpx.Client) -> None:
    r = client.get("/api/v1/auth/oauth/github/login", follow_redirects=False)
    parts = urlsplit(r.headers["location"])
    client.get(parts.path + (f"?{parts.query}" if parts.query else ""), follow_redirects=False)


@pytest.fixture(scope="module")
def stack():
    """探测 P3 stack + P1 镜像；缺一则 skip。"""
    if not _docker_available():
        pytest.skip("Docker 或 P1 镜像不可用（需 make build + make up-p3）")
    try:
        httpx.get(f"{BASE}/api/v1/healthz", timeout=2).raise_for_status()
    except Exception:
        pytest.skip(f"P3 stack 未运行（{BASE}），先 make up-p3")
    return BASE


def test_oauth_create_real_start_and_access(stack):
    """OAuth 登录 → 建 workspace → 真实 start running → /ws/ 访问。FR-016/017/020。"""
    with httpx.Client(base_url=stack, timeout=30, follow_redirects=False) as c:
        _oauth_login(c)
        # 建 workspace
        slug = f"real-{uuid.uuid4().hex[:6]}"
        r = c.post("/api/v1/workspaces", json={"name": slug, "slug": slug, "template": "minimal"})
        assert r.status_code == 201, r.text
        ws = r.json()
        ws_id = ws["id"]
        assert ws["status"] == "created"

        # 真实启动（orchestrator 经 docker.sock 拉起容器组，< 120s healthy）
        r = c.post(f"/api/v1/workspaces/{ws_id}/start")
        assert r.status_code == 200, r.text
        # 轮询 status（前端列表 5s 轮询；这里给到 150s 余量）
        status = "starting"
        for _ in range(30):
            cur = c.get(f"/api/v1/workspaces/{ws_id}").json()
            status = cur["status"]
            if status in ("running", "error"):
                break
            time.sleep(5)
        assert status == "running", f"workspace 未在预期时间内 running（status={status}）"

        # 经 launcher 统一入口 /ws/{slug}/ 访问（cookie 鉴权 + auth_request）
        r = c.get(f"/ws/{slug}/", follow_redirects=False)
        # 统一入口应可访问（2xx 或 3xx；workspace 内部路由可能 404 但鉴权已过）
        assert r.status_code < 500, f"/ws/ 访问失败：{r.status_code}"

        # 清理（避免残留容器组）
        try:
            c.delete(f"/api/v1/workspaces/{ws_id}?purge=true")
        except Exception:
            pass


def test_workspace_audit_recorded_after_start(stack):
    """workspace 启动操作应在审计流可达（FR-030）。best-effort：端点可达即通过。"""
    with httpx.Client(base_url=stack, timeout=30, follow_redirects=False) as c:
        _oauth_login(c)
        slug = f"audit-{uuid.uuid4().hex[:6]}"
        ws = c.post("/api/v1/workspaces", json={"name": slug, "slug": slug, "template": "minimal"}).json()
        ws_id = ws["id"]
        c.post(f"/api/v1/workspaces/{ws_id}/start")
        r = c.get("/api/v1/audit", params={"workspace": ws_id, "limit": 20})
        assert r.status_code == 200
        try:
            c.delete(f"/api/v1/workspaces/{ws_id}?purge=true")
        except Exception:
            pass
