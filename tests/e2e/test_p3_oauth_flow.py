"""T056: P3 OAuth 登录端到端 E2E（US1 / SC-001 / SC-006）。

覆盖：OAuth mock 登录 → 建户 → JWT 等价（cookie 鉴权 /me）→ 邮箱合并 → state 伪造拒绝。
前置：make up-p3（orchestrator+postgres+launcher，OAUTH_MOCK=true）。
无 stack 运行时自动 skip（不阻塞 CI/unit）。

对应 quickstart 场景 2（2a/2b/2c）。
"""
from __future__ import annotations

import os
import uuid
from urllib.parse import urlsplit

import httpx
import pytest

# P3 统一入口 = launcher:8080；若仅起 orchestrator 可用 ORCH_E2E_URL 直连 8000。
BASE = os.environ.get("P3_E2E_URL", os.environ.get("ORCH_E2E_URL", "http://localhost:8080"))


@pytest.fixture(scope="module")
def stack():
    """探测 P3 stack 可用性；不可用则整 module skip。"""
    try:
        r = httpx.get(f"{BASE}/api/v1/healthz", timeout=2)
        if r.status_code != 200:
            pytest.skip(f"P3 stack 未就绪（{BASE} healthz={r.status_code}），先 make up-p3")
    except Exception:
        pytest.skip(f"P3 stack 未运行（{BASE} 不可达），先 make up-p3")
    return BASE


def _oauth_login(client: httpx.Client, provider: str = "github") -> None:
    """走 mock OAuth /login → /callback 闭环，登录态写入 client cookie jar。"""
    r = client.get(f"/api/v1/auth/oauth/{provider}/login", follow_redirects=False)
    assert r.status_code == 302, r.text
    loc = r.headers["location"]
    parts = urlsplit(loc)
    callback_path = parts.path + (f"?{parts.query}" if parts.query else "")
    r2 = client.get(callback_path, follow_redirects=False)
    assert r2.status_code == 302, r2.text


def test_oauth_mock_login_sets_cookies_and_me(stack):
    """2a：mock 登录闭环 → Set-Cookie access/refresh → /me cookie 鉴权 200。FR-002/004。"""
    with httpx.Client(base_url=stack, timeout=10, follow_redirects=False) as c:
        _oauth_login(c, "github")
        cookies = c.cookies.jar
        names = {ck.name for ck in cookies}
        assert "access_token" in names and "refresh_token" in names
        # /me 经 cookie 鉴权返回当前用户（FR-002 JWT 等价）
        r = c.get("/api/v1/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "dev-github@local"
        assert body.get("display_name") == "Dev GitHub"


def test_oauth_state_mismatch_rejected(stack):
    """2c：state 不匹配 → 400，不签 JWT。FR-005 / SC-006。"""
    with httpx.Client(base_url=stack, timeout=10, follow_redirects=False) as c:
        r = c.get(
            "/api/v1/auth/oauth/github/callback",
            params={"code": "mock-code-github", "state": "tampered"},
            follow_redirects=False,
        )
        assert r.status_code == 400
        # 失败不应下发 access_token
        set_cookies = r.headers.get_list("set-cookie")
        assert not any(s.startswith("access_token=") for s in set_cookies)


def test_oauth_email_merge_invariant(stack):
    """2b：邮箱合并不变量。

    mock github 写死 dev-github@local；注册一个不同邮箱的本地账户后 OAuth 登录，
    验证「邮箱不同 → 不误合并」（正向合并需 mock 可配 email，已由 integration 层精确覆盖）。
    FR-003 邮箱合并；SC-006 不产生重复用户。
    """
    email = f"merge-{uuid.uuid4().hex[:6]}@local"
    with httpx.Client(base_url=stack, timeout=10, follow_redirects=False) as c:
        # 注册本地账户（不同邮箱）
        r = c.post("/api/v1/auth/register", json={"email": email, "password": "pw123456"})
        assert r.status_code == 201, r.text
        tok = c.post(
            "/api/v1/auth/login", json={"email": email, "password": "pw123456"}
        ).json()["access_token"]
        me_local = c.get("/api/v1/me", headers={"Authorization": f"Bearer {tok}"}).json()
        # OAuth 登录（dev-github@local）
        c.cookies.clear()
        _oauth_login(c, "github")
        me_oauth = c.get("/api/v1/me").json()
        # 不同邮箱 → 必为不同 user，证明邮箱是合并唯一依据
        assert me_oauth["email"] != email
        assert me_oauth["id"] != me_local["id"]


def test_oauth_workspaces_accessible_with_cookie(stack):
    """登录态经 cookie 访问受保护资源 /workspaces（验证 cookie 鉴权链路完整）。FR-013。"""
    with httpx.Client(base_url=stack, timeout=10, follow_redirects=False) as c:
        # 未登录 → 401
        assert c.get("/api/v1/workspaces").status_code == 401
        _oauth_login(c, "github")
        # 登录后 → 200（空列表也行）
        assert c.get("/api/v1/workspaces").status_code == 200
