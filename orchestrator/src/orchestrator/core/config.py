"""Orchestrator 配置（pydantic-settings，读取环境变量）。specs/002 research.md R1/R2/R4/R5/R7。"""
from functools import lru_cache
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict

# 开发态随机密钥缓存（进程级，避免签发与校验用不同密钥）
_cached_dev_secret: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    env: str = "dev"
    database_url: str = "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator"

    jwt_secret_key: str = ""
    jwt_alg: str = "HS256"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7

    workspace_port_start: int = 8100
    workspace_port_end: int = 8199
    workspace_retention_days: int = 7
    workspace_volume_root: str = "/tmp/sandbox-workspaces"

    auth_failure_mode: str = "fail-closed"

    orch_url: str = "http://localhost:8000"
    orch_port: int = 8000

    def resolved_jwt_secret(self) -> str:
        """已配置则用之；prod 缺失 fail-fast；dev 缺失则生成并缓存（进程级一致）。"""
        global _cached_dev_secret
        if self.jwt_secret_key:
            return self.jwt_secret_key
        if self.env == "prod":
            raise RuntimeError("JWT_SECRET_KEY must be set in prod environment")
        if _cached_dev_secret is None:
            _cached_dev_secret = secrets.token_urlsafe(32)
        return _cached_dev_secret


@lru_cache
def get_settings() -> Settings:
    return Settings()
