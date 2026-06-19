"""OAuth 邮箱合并/绑定/解绑。data-model.md §3, research.md R2。

核心：link_or_create_user 按 (provider, provider_user_id) → email 合并 → 建户 三段。
OAuth-only user 的 password_hash 存空串哨兵（列保持 NOT NULL，零迁移；bcrypt verify
空串永远失败 = 无法密码登录，语义等价 data-model §2.2 的 NULL）。
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.models.oauth_account import OAuthAccount
from orchestrator.models.user import User
from orchestrator.services.oauth_provider import UserInfo


async def link_or_create_user(session: AsyncSession, info: UserInfo) -> User:
    """OAuth 回调主入口：定位/合并/建户。

    data-model §3：
      1. 查 oauth_accounts by (provider, provider_user_id) → 命中复用 user_id
      2. 否则查 users by LOWER(email) → 命中绑定（刷新 profile）
      3. 否则建 user（password_hash="" 哨兵）+ oauth_accounts
    """
    # 1) 已绑定 → 复用
    existing_oa = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == info.provider,
            OAuthAccount.provider_user_id == info.provider_user_id,
        )
    )
    if existing_oa:
        user = await session.get(User, existing_oa.user_id)
        if user is None:
            # FK 孤儿（理论不应发生）：当作未绑定，继续走合并
            pass
        else:
            _refresh_profile(user, info)
            await session.commit()
            return user

    # 2) 邮箱合并
    user_by_email: User | None = None
    if info.email:
        user_by_email = await session.scalar(
            select(User).where(func.lower(User.email) == info.email.lower())
        )
    if user_by_email is not None:
        _refresh_profile(user_by_email, info)
        await _create_oauth_account(session, user_by_email, info)
        await session.commit()
        return user_by_email

    # 3) 全新建户
    new_user = User(
        email=(info.email or f"{info.provider}-{info.provider_user_id}@oauth.local"),
        password_hash="",  # OAuth-only 哨兵
        display_name=info.display_name,
        avatar_url=info.avatar_url,
    )
    session.add(new_user)
    await session.flush()  # 取 new_user.id
    try:
        await _create_oauth_account(session, new_user, info)
    except IntegrityError:
        # 并发：UNIQUE(provider, provider_user_id) 冲突 → 回查复用（TOCTOU 兜底）
        await session.rollback()
        return await link_or_create_user(session, info)
    await session.commit()
    return new_user


async def bind_to_user(session: AsyncSession, user: User, info: UserInfo) -> OAuthAccount:
    """已登录用户绑定新 provider。若 (provider,pid) 已绑他人 → 409。"""
    existing = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == info.provider,
            OAuthAccount.provider_user_id == info.provider_user_id,
        )
    )
    if existing and existing.user_id != user.id:
        raise HTTPException(status_code=409, detail={"error": {"code": "oauth_already_bound"}})
    oa = await _create_oauth_account(session, user, info)
    await session.commit()
    return oa


async def list_accounts(session: AsyncSession, user: User) -> list[OAuthAccount]:
    res = await session.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == user.id)
    )
    return list(res.scalars().all())


async def unbind(session: AsyncSession, user: User, provider: str) -> None:
    """解绑。解绑前检查：用户是否还有 password 或其他 provider，否则 409 拒绝。"""
    row = await session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.user_id == user.id, OAuthAccount.provider == provider,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "oauth_not_bound"}})
    # 失去该 provider 后是否仍有登录方式：有密码（非空哨兵）或其余 provider
    has_password = bool(user.password_hash)
    other_count = await session.scalar(
        select(func.count(OAuthAccount.id)).where(
            OAuthAccount.user_id == user.id, OAuthAccount.provider != provider,
        )
    )
    if not has_password and not other_count:
        raise HTTPException(status_code=409, detail={"error": {"code": "last_login_method"}})
    await session.delete(row)
    await session.commit()


# ---- 内部 ----
def _refresh_profile(user: User, info: UserInfo) -> None:
    """OAuth 回调刷新 user 的 profile 字段（display_name/avatar_url）。"""
    if info.display_name:
        user.display_name = info.display_name
    if info.avatar_url:
        user.avatar_url = info.avatar_url


async def _create_oauth_account(
    session: AsyncSession, user: User, info: UserInfo,
) -> OAuthAccount:
    oa = OAuthAccount(
        provider=info.provider,
        provider_user_id=info.provider_user_id,
        user_id=user.id,
        email=info.email,
        raw_profile=info.raw,
    )
    session.add(oa)
    await session.flush()
    return oa
