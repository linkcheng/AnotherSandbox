"""T027: security 测试（bcrypt + JWT 签发/校验）。research.md R5。"""
import jwt
import pytest

from orchestrator.core import security


def test_hash_and_verify_password():
    h = security.hash_password("secret")
    assert h != "secret"
    assert security.verify_password("secret", h) is True
    assert security.verify_password("wrong", h) is False


def test_create_and_decode_access_token():
    tok = security.create_access_token("user-123")
    payload = security.decode_token(tok)
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"
    assert "exp" in payload and "iat" in payload


def test_create_refresh_token_type_claim():
    payload = security.decode_token(security.create_refresh_token("u1"))
    assert payload["type"] == "refresh"


def test_decode_invalid_token_raises():
    with pytest.raises(jwt.PyJWTError):
        security.decode_token("not.a.valid.token")


def test_token_wrong_signature_rejected():
    tok = security.create_access_token("u1")
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(tok, "wrong-secret", algorithms=["HS256"])


def test_verify_password_invalid_hash_returns_false():
    assert security.verify_password("x", "not-a-hash") is False
