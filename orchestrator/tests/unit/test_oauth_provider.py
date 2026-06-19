"""T019: OAuth provider 单测。

- 真实 provider：respx mock IdP token/userinfo 端点，验证 authorize_url 含 state/PKCE、
  token 交换、userinfo 解析（GitHub/Google）。
- MockOAuthProvider：固定 code/userinfo，走真实建户/签 JWT 路径。
research.md R1/R9。
"""
import httpx
import pytest
import respx

from orchestrator.services.oauth_provider import (
    MockOAuthProvider, UserInfo, get_oauth_provider,
)


# ---------- 真实 GitHub provider ----------

def test_github_authorize_url_has_state_and_pkce():
    p = get_oauth_provider("github", mock=False)
    url = p.get_authorization_url(state="xyz-state", redirect_uri="http://app/cb")
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "state=xyz-state" in url
    # PKCE code_challenge（S256）
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "client_id=" in url


def test_github_authorize_url_rejects_unknown_provider():
    """provider 白名单外报错（router 层 400，service 层 ValueError）。"""
    from orchestrator.services.oauth_provider import RealOAuthProvider
    with pytest.raises(ValueError):
        RealOAuthProvider("facebook")


@respx.mock
@pytest.mark.asyncio
async def test_github_exchange_and_fetch_userinfo():
    p = get_oauth_provider("github", mock=False)
    # 1) token 端点
    respx.post("https://github.com/login/oauth/access_token").mock(
        return_value=httpx.Response(
            200, json={"access_token": "gho_token123", "token_type": "bearer"},
            headers={"content-type": "application/json"},
        )
    )
    # 2) userinfo 端点
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={
            "id": 12345, "login": "alice", "name": "Alice",
            "email": "alice@example.com", "avatar_url": "https://gh/a.png",
        })
    )
    info: UserInfo = await p.exchange_and_fetch_userinfo(
        code="abc-code", state="xyz", redirect_uri="http://app/cb",
    )
    assert info.provider == "github"
    assert info.provider_user_id == "12345"
    assert info.email == "alice@example.com"
    assert info.display_name == "Alice"
    assert info.avatar_url == "https://gh/a.png"
    assert info.raw["login"] == "alice"


# ---------- 真实 Google provider ----------

@respx.mock
@pytest.mark.asyncio
async def test_google_exchange_and_fetch_userinfo():
    p = get_oauth_provider("google", mock=False)
    respx.post("https://oauth2.googleapis.com/token").mock(
        return_value=httpx.Response(200, json={"access_token": "ya29_token"})
    )
    respx.get("https://www.googleapis.com/oauth2/v3/userinfo").mock(
        return_value=httpx.Response(200, json={
            "sub": "g-67890", "email": "bob@gmail.com",
            "name": "Bob", "picture": "https://g/b.png",
        })
    )
    info = await p.exchange_and_fetch_userinfo(
        code="g-code", state="s1", redirect_uri="http://app/cb",
    )
    assert info.provider == "google"
    assert info.provider_user_id == "g-67890"
    assert info.email == "bob@gmail.com"
    assert info.avatar_url == "https://g/b.png"


def test_google_authorize_url():
    p = get_oauth_provider("google", mock=False)
    url = p.get_authorization_url(state="st", redirect_uri="http://app/cb")
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")


# ---------- MockOAuthProvider ----------

def test_mock_provider_authorize_url_points_to_callback():
    """mock 模式 login 直接 302 到自身 callback（R9）。

    router 传入的 redirect_uri 已是完整 callback URL（{oauth_redirect_url}/{provider}/callback），
    mock 仅附加 code/state，不再二次拼路径。
    """
    p = get_oauth_provider("github", mock=True)
    assert isinstance(p, MockOAuthProvider)
    url = p.get_authorization_url(
        state="mystate",
        redirect_uri="http://app/api/v1/auth/oauth/github/callback",
    )
    # 指向 callback 且带 mock code + state，路径不重复
    assert url.startswith("http://app/api/v1/auth/oauth/github/callback?")
    assert "code=mock-code-github" in url
    assert "state=mystate" in url


@pytest.mark.asyncio
async def test_mock_provider_exchange_returns_fixed_userinfo():
    p = get_oauth_provider("github", mock=True)
    info = await p.exchange_and_fetch_userinfo(
        code="mock-code-github", state="s", redirect_uri="http://app/cb",
    )
    assert info.provider == "github"
    assert info.provider_user_id == "mock-github-001"
    assert info.email == "dev-github@local"
    assert "GitHub" in info.display_name


@pytest.mark.asyncio
async def test_mock_provider_google():
    p = get_oauth_provider("google", mock=True)
    info = await p.exchange_and_fetch_userinfo(
        code="mock-code-google", state="s", redirect_uri="http://app/cb",
    )
    assert info.provider == "google"
    assert info.provider_user_id == "mock-google-001"


def test_get_oauth_provider_unknown_raises():
    with pytest.raises(ValueError):
        get_oauth_provider("facebook", mock=False)
