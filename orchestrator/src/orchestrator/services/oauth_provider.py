"""OAuth provider 封装：GitHub/Google（Authorization Code + PKCE）+ Mock。

research.md R1（authlib + PKCE）/ R9（mock 开关）。
对外契约：
- get_authorization_url(provider, state, redirect) -> str
- exchange_and_fetch_userinfo(provider, code, state, redirect) -> UserInfo

设计：用 authlib 的 PKCE 工具生成 code_challenge；authorize URL 手拼（更可控，避免
authlib client registry 的隐式状态）；token/userinfo 用 httpx async 调 IdP。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from secrets import token_urlsafe
from urllib.parse import urlencode

import httpx
from authlib.oauth2.rfc7636.challenge import create_s256_code_challenge

from orchestrator.core.config import get_settings

SUPPORTED_PROVIDERS = ("github", "google")


# 各 IdP 的固定端点（research.md 指定）
_AUTHORIZE_URLS = {
    "github": "https://github.com/login/oauth/authorize",
    "google": "https://accounts.google.com/o/oauth2/v2/auth",
}
_TOKEN_URLS = {
    "github": "https://github.com/login/oauth/access_token",
    "google": "https://oauth2.googleapis.com/token",
}
_USERINFO_URLS = {
    "github": "https://api.github.com/user",
    "google": "https://www.googleapis.com/oauth2/v3/userinfo",
}
# Google userinfo scope 需显式声明（GitHub 默认返 user）
_SCOPES = {
    "github": "read:user user:email",
    "google": "openid email profile",
}


@dataclass
class UserInfo:
    """IdP 回传的归一化用户信息（oauth_linker 合并依据）。"""
    provider: str
    provider_user_id: str
    email: str | None
    display_name: str | None
    avatar_url: str | None
    raw: dict = field(default_factory=dict)


class _BaseOAuthProvider:
    """provider 接口基类。具体实现：RealOAuthProvider / MockOAuthProvider。"""

    def __init__(self, provider: str) -> None:
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"unsupported oauth provider: {provider}")
        self.provider = provider

    def get_authorization_url(self, *, state: str, redirect_uri: str) -> str:  # pragma: no cover - 接口
        raise NotImplementedError

    async def exchange_and_fetch_userinfo(  # pragma: no cover - 接口
        self, *, code: str, state: str, redirect_uri: str,
    ) -> UserInfo:
        raise NotImplementedError


class RealOAuthProvider(_BaseOAuthProvider):
    """真实 GitHub/Google：authlib PKCE + httpx 调 IdP。"""

    def get_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        settings = get_settings()
        client_id = self._client_id(settings)
        # PKCE：S256 code_challenge（R1）。verifier 用 token_urlsafe 生成（RFC 7636），
        # 存实例供 exchange 复用（单次 login 流）。
        verifier = token_urlsafe(48)
        challenge = create_s256_code_challenge(verifier)
        self._code_verifier = verifier
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": _SCOPES[self.provider],
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{_AUTHORIZE_URLS[self.provider]}?{urlencode(params)}"

    async def exchange_and_fetch_userinfo(
        self, *, code: str, state: str, redirect_uri: str,
    ) -> UserInfo:
        settings = get_settings()
        token = await self._exchange_code(code, redirect_uri, settings)
        raw = await self._fetch_userinfo(token)
        return self._parse_userinfo(raw)

    # ---- 内部 ----
    def _client_id(self, settings) -> str:
        return (
            settings.oauth_github_client_id if self.provider == "github"
            else settings.oauth_google_client_id
        )

    def _client_secret(self, settings) -> str:
        return (
            settings.oauth_github_client_secret if self.provider == "github"
            else settings.oauth_google_client_secret
        )

    async def _exchange_code(self, code: str, redirect_uri: str, settings) -> str:
        data = {
            "client_id": self._client_id(settings),
            "client_secret": self._client_secret(settings),
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        verifier = getattr(self, "_code_verifier", None)
        if verifier:
            data["code_verifier"] = verifier
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(_TOKEN_URLS[self.provider], data=data, headers=headers)
        if r.status_code != 200:
            raise OauthExchangeError(f"token endpoint {r.status_code}")
        body = r.json()
        token = body.get("access_token")
        if not token:
            raise OauthExchangeError("no access_token in response")
        return token

    async def _fetch_userinfo(self, access_token: str) -> dict:
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(_USERINFO_URLS[self.provider], headers=headers)
        if r.status_code != 200:
            raise OauthExchangeError(f"userinfo endpoint {r.status_code}")
        return r.json()

    def _parse_userinfo(self, raw: dict) -> UserInfo:
        if self.provider == "github":
            return UserInfo(
                provider="github",
                provider_user_id=str(raw.get("id", "")),
                email=raw.get("email"),
                display_name=raw.get("name") or raw.get("login"),
                avatar_url=raw.get("avatar_url"),
                raw=raw,
            )
        # google
        return UserInfo(
            provider="google",
            provider_user_id=str(raw.get("sub", "")),
            email=raw.get("email"),
            display_name=raw.get("name"),
            avatar_url=raw.get("picture"),
            raw=raw,
        )


class MockOAuthProvider(_BaseOAuthProvider):
    """OAUTH_MOCK=true 时的离线 provider（R9）。

    - get_authorization_url：302 到自身 callback，带固定 mock code + state。
    - exchange_and_fetch_userinfo：不调 IdP，返回预设 userinfo，走真实建户/签 JWT 路径。
    """

    def get_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        # router 传入的 redirect_uri 已是完整 callback URL（{oauth_redirect_url}/{provider}/callback）。
        # mock 模式直接 302 到该 callback，仅附加 code/state（R9），不再二次拼路径。
        params = {
            "code": self._mock_code(),
            "state": state,
        }
        return f"{redirect_uri}?{urlencode(params)}"

    async def exchange_and_fetch_userinfo(
        self, *, code: str, state: str, redirect_uri: str,
    ) -> UserInfo:
        # mock 模式忽略 code/state 真实性，直接返预设 userinfo
        return self._preset_userinfo()

    def _mock_code(self) -> str:
        return f"mock-code-{self.provider}"

    def _preset_userinfo(self) -> UserInfo:
        # 品牌正确大写（GitHub/Google）
        name = {"github": "GitHub", "google": "Google"}[self.provider]
        return UserInfo(
            provider=self.provider,
            provider_user_id=f"mock-{self.provider}-001",
            email=f"dev-{self.provider}@local",
            display_name=f"Dev {name}",
            avatar_url=None,
            raw={"mock": True, "provider": self.provider},
        )


def get_oauth_provider(provider: str, *, mock: bool | None = None) -> _BaseOAuthProvider:
    """工厂：按 provider + OAUTH_MOCK 开关返回实例。

    mock=None 时读 settings.oauth_mock（默认 True，dev）。router 调用传 None。
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"unsupported oauth provider: {provider}")
    if mock is None:
        mock = get_settings().oauth_mock
    return MockOAuthProvider(provider) if mock else RealOAuthProvider(provider)


class OauthExchangeError(Exception):
    """token 交换 / userinfo 取数失败（router 映射 401/502）。"""
