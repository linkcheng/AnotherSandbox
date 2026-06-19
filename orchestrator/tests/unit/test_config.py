"""T008: Settings 配置测试（FR-007 基础, research.md R1/R2/R4/R7）。"""
import pytest

from orchestrator.core.config import Settings, get_settings


def test_settings_defaults():
    s = Settings()
    assert s.workspace_port_start == 8100
    assert s.workspace_port_end == 8199
    assert s.workspace_retention_days == 7
    assert s.auth_failure_mode == "fail-closed"
    assert s.jwt_alg == "HS256"
    assert s.access_token_ttl_min == 15
    assert s.refresh_token_ttl_days == 7
    assert s.env == "dev"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("WORKSPACE_PORT_START", "9000")
    monkeypatch.setenv("AUTH_FAILURE_MODE", "fail-open")
    monkeypatch.setenv("WORKSPACE_RETENTION_DAYS", "30")
    s = Settings()
    assert s.workspace_port_start == 9000
    assert s.auth_failure_mode == "fail-open"
    assert s.workspace_retention_days == 30


def test_resolved_jwt_secret_dev_random_when_empty():
    s = Settings(env="dev", jwt_secret_key="")
    secret = s.resolved_jwt_secret()
    assert isinstance(secret, str) and secret  # 非空随机


def test_resolved_jwt_secret_prod_missing_raises():
    s = Settings(env="prod", jwt_secret_key="")
    with pytest.raises(RuntimeError):
        s.resolved_jwt_secret()


def test_resolved_jwt_secret_uses_configured():
    s = Settings(jwt_secret_key="my-fixed-key")
    assert s.resolved_jwt_secret() == "my-fixed-key"


def test_get_settings_is_cached():
    assert get_settings() is get_settings()
