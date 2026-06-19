"""Orchestrator 配置（pydantic-settings，读取环境变量）。specs/002 research.md R1/R2/R4。"""
from functools import lru_cache
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # 运行环境
    env: str = "dev"  # dev | prod

    # 数据库
    database_url: str = "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator"

    # JWT（R5）
    jwt_secret_key: str = ""  # 空 → 开发态随机生成；prod 必填（R7）
    jwt_alg: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7

    # 端口分配（R2）
    workspace_port_start: int = 8100
    workspace_port_end: int = 8199

    # workspace 生命周期（R1）
    workspace_retention_days: int = 7
    workspace_volume_root: str = "/tmp/sandbox-workspaces"

    # 鉴权降级（R4）
    auth_failure_mode: str = "fail-closed"  # fail-closed | fail-open

    # Orchestrator 自身
    orch_url: str = "http://localhost:8000"
    orch_port: int = 8000

    def resolved_jwt_secret(self) -> str:
        """返回有效 JWT 密钥：已配置则用之；prod 缺失则 fail-fast；dev 缺失则随机生成。"""
        if self.jwt_secret_key:
            return self.jwt_secret_key
        if self.env == "prod":
            raise RuntimeError("JWT_SECRET_KEY must be set in prod environment")
        return secrets.token_urlsafe(32)


@lru_cache
def get_settings() -> Settings:
    return Settings()
