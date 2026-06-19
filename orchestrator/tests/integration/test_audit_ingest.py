"""T057: audit ingest/query 集成测试。contracts/audit-ingest.md。"""
import uuid

import pytest

pytestmark = pytest.mark.integration


def _setup(client):
    email = f"a{uuid.uuid4().hex[:8]}@e.c"
    client.post("/api/v1/auth/register", json={"email": email, "password": "pw"})
    token = client.post("/api/v1/auth/login", json={"email": email, "password": "pw"}).json()["access_token"]
    ws = client.post("/api/v1/workspaces", json={"name": "a"}, headers={"Authorization": f"Bearer {token}"}).json()
    return token, ws["id"]


def test_ingest_writes_and_query_returns(client):
    token, ws_id = _setup(client)
    r = client.post("/api/v1/audit/ingest", json={
        "workspace_id": ws_id, "event_type": "shell.exec", "source": "cap-terminal",
        "detail": {"command": "echo hi", "exit_code": 0}, "success": True,
    })
    assert r.status_code == 201, r.text
    assert r.json()["event_type"] == "shell.exec"

    r2 = client.get("/api/v1/audit", params={"workspace_id": ws_id}, headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    assert len(r2.json()) >= 1
    assert r2.json()[0]["detail"]["command"] == "echo hi"


def test_ingest_invalid_source_rejected(client):
    _, ws_id = _setup(client)
    r = client.post("/api/v1/audit/ingest", json={
        "workspace_id": ws_id, "event_type": "shell.exec", "source": "evil",
        "detail": {}, "success": True,
    })
    assert r.status_code == 400


def test_query_forbidden_without_ownership(client):
    token, ws_id = _setup(client)  # user A
    email_b = f"b{uuid.uuid4().hex[:8]}@e.c"
    client.post("/api/v1/auth/register", json={"email": email_b, "password": "pw"})
    token_b = client.post("/api/v1/auth/login", json={"email": email_b, "password": "pw"}).json()["access_token"]
    r = client.get("/api/v1/audit", params={"workspace_id": ws_id}, headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 403
