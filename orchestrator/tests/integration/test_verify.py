"""T048: /verify auth_request 目标测试。contracts/trusted-headers.md, research.md R8。"""
import uuid

import pytest

pytestmark = pytest.mark.integration


def _setup_user_and_ws(client):
    email = f"v{uuid.uuid4().hex[:8]}@e.c"
    client.post("/api/v1/auth/register", json={"email": email, "password": "pw"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "pw"}).json()["access_token"]
    ws = client.post("/api/v1/workspaces", json={"name": "v"}, headers={"Authorization": f"Bearer {token}"}).json()
    return token, ws["id"]


def test_verify_sets_trusted_headers(client):
    token, ws_id = _setup_user_and_ws(client)
    r = client.post(
        "/api/v1/verify",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": ws_id},
    )
    assert r.status_code == 200, r.text
    assert r.headers["x-user-id"]
    assert r.headers["x-workspace-id"] == ws_id
    assert r.headers["x-permissions"] == "owner"


def test_verify_no_token_401(client):
    r = client.post("/api/v1/verify", headers={"X-Workspace-Id": str(uuid.uuid4())})
    assert r.status_code == 401


def test_verify_missing_workspace_header_400(client):
    token, _ = _setup_user_and_ws(client)
    r = client.post("/api/v1/verify", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400


def test_verify_other_user_forbidden_403(client):
    token, ws_id = _setup_user_and_ws(client)
    email_b = f"b{uuid.uuid4().hex[:8]}@e.c"
    client.post("/api/v1/auth/register", json={"email": email_b, "password": "pw"})
    token_b = client.post("/api/v1/auth/login", json={"email": email_b, "password": "pw"}).json()["access_token"]
    r = client.post(
        "/api/v1/verify",
        headers={"Authorization": f"Bearer {token_b}", "X-Workspace-Id": ws_id},
    )
    assert r.status_code == 403


def test_verify_bad_token_401(client):
    r = client.post(
        "/api/v1/verify",
        headers={"Authorization": "Bearer garbage", "X-Workspace-Id": str(uuid.uuid4())},
    )
    assert r.status_code == 401
