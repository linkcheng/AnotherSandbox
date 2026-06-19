"""T030/T034: 认证流程集成测试。contracts/orchestrator-rest-api §1, research.md R5。"""
import uuid

import pytest

pytestmark = pytest.mark.integration


def test_register_duplicate_login_wrong_rotation(client):
    email = f"u{uuid.uuid4().hex[:8]}@example.com"

    # register 201
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "pw-correct"})
    assert r.status_code == 201, r.text
    assert r.json()["email"] == email

    # duplicate email → 409
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "x"})
    assert r.status_code == 409

    # login 200 + tokens
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "pw-correct"})
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["expires_in"] > 0
    old_refresh = tokens["refresh_token"]

    # wrong password → 401
    r = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
    assert r.status_code == 401

    # refresh rotation → 200 + 新 token；旧 refresh 再用 → 401
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200, r.text
    assert r.json()["refresh_token"] != old_refresh

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 401

    # 篡改 refresh → 401
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert r.status_code == 401


def test_email_normalized_to_lower(client):
    email = f"UPPER{uuid.uuid4().hex[:6]}@EXAMPLE.COM"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "pw"})
    assert r.status_code == 201
    assert r.json()["email"] == email.lower()
    # 用原始大写登录也能命中（login 前 lower）
    r2 = client.post("/api/v1/auth/login", json={"email": email, "password": "pw"})
    assert r2.status_code == 200
