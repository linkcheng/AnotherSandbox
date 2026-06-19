"""OAuth 路由（5 端点）。contracts/oauth-rest-api, research.md R1/R3/R9。

prefix /api/v1/auth/oauth，tag oauth。
- GET /{provider}/login：302 到 IdP（mock 时 302 自身 callback），Set-Cookie oauth_state
- GET /{provider}/callback：state 校验→exchange→linker→签 JWT→Set-Cookie→302
- GET /accounts：列已绑定 provider（需登录 cookie）
- POST /{provider}/bind：已登录用户发起绑定
- DELETE /{provider}/unbind：解绑（409 若失去最后登录方式）

state 设计（KISS）：随机 token 经 HMAC 签名，cookie 存签名值，回调比对一致性。
redirect 目标页不编码进 state（避免解析复杂度）；成功后固定回 /。
"""
from __future__ import annotations

import hmac
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.core.config import get_settings
from orchestrator.core.db import get_session
from orchestrator.core.security import create_access_token, create_refresh_token
from orchestrator.deps import get_current_user_optional_cookie
from orchestrator.models.user import User
from orchestrator.routers.auth import set_session_cookies
from orchestrator.schemas.oauth import OAuthAccountOut, OAuthAccountsResponse
from orchestrator.services.oauth_linker import (
    bind_to_user, link_or_create_user, list_accounts, unbind,
)
from orchestrator.services.oauth_provider import (
    SUPPORTED_PROVIDERS, OauthExchangeError, get_oauth_provider,
)

router = APIRouter(prefix="/api/v1/auth/oauth", tags=["oauth"])
_settings = get_settings()

# state cookie 名 + TTL（秒）
_STATE_COOKIE = "oauth_state"
_STATE_TTL = 600  # 10 分钟


def _build_redirect_uri(provider: str) -> str:
    """构造回调绝对 URL（oauth_redirect_url 基址 + /{provider}/callback）。"""
    base = _settings.oauth_redirect_url.rstrip("/")
    return f"{base}/{provider}/callback"


def _new_signed_state() -> str:
    """生成随机 state 并用 HMAC 签名（防伪造）。"""
    raw = secrets.token_urlsafe(16)
    sig = hmac.new(_settings.resolved_jwt_secret().encode(), raw.encode(), "md5").hexdigest()
    return f"{raw}.{sig}"


def _state_is_valid(signed: str) -> bool:
    """校验 state 签名。"""
    if "." not in signed:
        return False
    raw, sig = signed.rsplit(".", 1)
    expected = hmac.new(_settings.resolved_jwt_secret().encode(), raw.encode(), "md5").hexdigest()
    return hmac.compare_digest(sig, expected)


@router.get("/{provider}/login")
async def oauth_login(
    provider: str,
    redirect: str = Query("/", description="登录成功后回到的 launcher 页面（MVP 固定回 /）"),
):
    """发起 OAuth 登录：302 到 IdP（mock 时 302 自身 callback）。FR-004。"""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_provider"}})
    state = _new_signed_state()
    p = get_oauth_provider(provider)
    url = p.get_authorization_url(state=state, redirect_uri=_build_redirect_uri(provider))
    resp = RedirectResponse(url=url, status_code=302)
    resp.set_cookie(
        _STATE_COOKIE, state, max_age=_STATE_TTL,
        httponly=True, samesite="lax", secure=_settings.env == "prod",
    )
    return resp


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """OAuth 回调：校验 state→exchange→linker→签 JWT→Set-Cookie→302。FR-005。"""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_provider"}})
    cookie_state = request.cookies.get(_STATE_COOKIE)
    # state 不匹配/被篡改 → 400
    if not cookie_state or cookie_state != state or not _state_is_valid(cookie_state):
        raise HTTPException(status_code=400, detail={"error": {"code": "state_mismatch"}})

    p = get_oauth_provider(provider)
    try:
        info = await p.exchange_and_fetch_userinfo(
            code=code, state=state, redirect_uri=_build_redirect_uri(provider),
        )
    except OauthExchangeError:
        # code 失效/IdP 异常 → 重定向登录页带 error（FR-005）
        resp = RedirectResponse(url="/login?error=oauth_failed", status_code=302)
        resp.delete_cookie(_STATE_COOKIE)
        return resp

    user = await link_or_create_user(session, info)

    # 签等价 JWT（复用 P2 security，SC-006）
    access = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))

    resp = RedirectResponse(url="/", status_code=302)
    set_session_cookies(resp, access, refresh)
    resp.delete_cookie(_STATE_COOKIE)
    return resp


@router.get("/accounts", response_model=OAuthAccountsResponse)
async def oauth_accounts(
    user: User = Depends(get_current_user_optional_cookie),
    session: AsyncSession = Depends(get_session),
):
    """列出当前登录用户绑定的 provider。FR-006。"""
    accounts = await list_accounts(session, user)
    return OAuthAccountsResponse(
        accounts=[OAuthAccountOut.model_validate(a) for a in accounts]
    )


@router.post("/{provider}/bind")
async def oauth_bind(
    provider: str,
    user: User = Depends(get_current_user_optional_cookie),
    session: AsyncSession = Depends(get_session),
):
    """已登录用户发起绑定。mock 模式直接绑定预设身份；真实模式 MVP 暂走 link_or_create 路径。

    真实 IdP 完整绑定（302→callback 携带已登录态→bind_to_user）超出 MVP 范围，
    此处 mock 模式直接复用 bind_to_user 校验逻辑。
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_provider"}})
    if _settings.oauth_mock:
        from orchestrator.services.oauth_provider import MockOAuthProvider
        info = MockOAuthProvider(provider)._preset_userinfo()
        await bind_to_user(session, user, info)
        return {"bound": provider}
    raise HTTPException(status_code=501, detail={"error": {"code": "bind_via_idp_not_implemented"}})


@router.delete("/{provider}/unbind")
async def oauth_unbind(
    provider: str,
    user: User = Depends(get_current_user_optional_cookie),
    session: AsyncSession = Depends(get_session),
):
    """解绑。409 若失去最后登录方式。FR-006。"""
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail={"error": {"code": "invalid_provider"}})
    await unbind(session, user, provider)
    return {"unbound": provider}
