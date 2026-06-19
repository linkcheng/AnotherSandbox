"""T042/T044: workspace CRUD + lifecycle 集成测试（mock compose_runner 避免 Docker）。

注：session 级 PG 复用，port_allocator 跨 test 累积分配 → port 递增，断言用范围非固定值。
"""
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.core.config import get_settings
from orchestrator.services.compose_runner import ComposeResult

pytestmark = pytest.mark.integration


def _register_login(client) -> str:
    email = f"w{uuid.uuid4().hex[:8]}@e.c"
    client.post("/api/v1/auth/register", json={"email": email, "password": "pw"})
    return client.post("/api/v1/auth/login", json={"email": email, "password": "pw"}).json()["access_token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, name="dev") -> dict:
    r = client.post("/api/v1/workspaces", json={"name": name}, headers=_h(token))
    assert r.status_code == 201, r.text
    return r.json()


def test_create_requires_auth_and_port_in_range(client):
    assert client.post("/api/v1/workspaces", json={"name": "x"}).status_code == 401
    token = _register_login(client)
    ws = _create(client, token, "alice-dev")
    assert ws["status"] == "created"
    assert ws["slug"].startswith("alice-dev-")
    s = get_settings()
    assert s.workspace_port_start <= ws["external_port"] <= s.workspace_port_end


def test_list_and_get(client):
    token = _register_login(client)
    h = _h(token)
    ws = _create(client, token, "list-test")
    wid = ws["id"]
    r = client.get("/api/v1/workspaces", headers=h)
    assert r.status_code == 200
    assert any(w["id"] == wid for w in r.json())
    r2 = client.get(f"/api/v1/workspaces/{wid}", headers=h)
    assert r2.status_code == 200 and r2.json()["id"] == wid


def test_other_user_forbidden(client):
    owner_tok = _register_login(client)
    ws = _create(client, owner_tok, "owned")
    wid = ws["id"]
    other_tok = _register_login(client)  # 另一用户
    r = client.get(f"/api/v1/workspaces/{wid}", headers=_h(other_tok))
    assert r.status_code == 403  # 非归属


def test_start_stop_with_mocked_compose(client):
    token = _register_login(client)
    h = _h(token)
    wid = _create(client, token, "dev")["id"]
    ok = ComposeResult(success=True, returncode=0)
    with patch("orchestrator.routers.workspaces.compose_runner.up", new=AsyncMock(return_value=ok)):
        r = client.post(f"/api/v1/workspaces/{wid}/start", headers=h)
        assert r.status_code == 200 and r.json()["status"] == "running"
    with patch("orchestrator.routers.workspaces.compose_runner.down", new=AsyncMock(return_value=ok)):
        r2 = client.post(f"/api/v1/workspaces/{wid}/stop", headers=h)
        assert r2.status_code == 200 and r2.json()["status"] == "stopped"


def test_get_nonexistent_returns_404(client):
    token = _register_login(client)
    assert client.get(f"/api/v1/workspaces/{uuid.uuid4()}", headers=_h(token)).status_code == 404
