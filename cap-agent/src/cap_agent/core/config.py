"""cap-agent 配置（pydantic-settings）。"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量加载的运行时配置。"""

    model_config = SettingsConfigDict(
        env_prefix="CAP_AGENT_",
        env_file=".env",
        extra="ignore",
    )

    # 下游服务 URL（容器内 DNS）
    terminal_url: str = "http://cap-terminal:7682"
    browser_cdp_url: str = "http://cap-browser:9222"

    # GUI（pyautogui 共享 cap-browser 的 X display）
    gui_display: str = ":1"

    # 鉴权（P1 固定 none；P2 切换 orchestrator）
    auth_mode: str = "none"


settings = Settings()
