"""cap-agent 配置（pydantic-settings）单元测试。

对应 spec.md FR-016、tasks.md T014。
"""
from __future__ import annotations

import pytest

from cap_agent.core.config import Settings, settings


def test_default_settings_match_p1_contract() -> None:
    """默认配置匹配 P1 spec：终端/浏览器/Display/auth_mode。"""
    cfg = Settings()

    assert cfg.terminal_url == "http://cap-terminal:7682"
    assert cfg.browser_cdp_url == "http://cap-browser:9222"
    assert cfg.gui_display == ":1"
    assert cfg.auth_mode == "none"


def test_module_singleton_uses_defaults() -> None:
    """模块级 settings 单例加载默认值。"""
    assert settings.auth_mode == "none"


def test_env_prefix_cap_agent_is_respected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CAP_AGENT_ 前缀的环境变量会覆盖默认值。"""
    monkeypatch.setenv("CAP_AGENT_AUTH_MODE", "orchestrator")
    monkeypatch.setenv("CAP_AGENT_TERMINAL_URL", "http://custom:1")

    cfg = Settings()

    assert cfg.auth_mode == "orchestrator"
    assert cfg.terminal_url == "http://custom:1"


def test_unprefixed_env_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """无 CAP_AGENT_ 前缀的环境变量被忽略。"""
    monkeypatch.setenv("AUTH_MODE", "orchestrator")

    cfg = Settings()

    assert cfg.auth_mode == "none"
