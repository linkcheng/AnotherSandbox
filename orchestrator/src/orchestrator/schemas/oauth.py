"""OAuth Pydantic schemas。contracts/oauth-rest-api §3/§4, data-model.md §2.1。"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OAuthAccountOut(BaseModel):
    """某条 oauth_accounts 记录的对外视图（账户绑定/解绑 UI）。"""
    model_config = ConfigDict(from_attributes=True)
    provider: str
    email: str | None
    created_at: datetime


class OAuthAccountsResponse(BaseModel):
    """GET /api/v1/auth/oauth/accounts 响应。"""
    accounts: list[OAuthAccountOut]


class MeOut(BaseModel):
    """GET /api/v1/me 响应：当前 user（含 OAuth profile 字段）。

    不复用 P2 UserOut（其不含 display_name/avatar_url，保持 CLI 兼容）。
    """
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    created_at: datetime
