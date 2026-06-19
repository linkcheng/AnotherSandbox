"""T021: oauth_linker 邮箱合并逻辑单测（mock AsyncSession，不依赖 DB）。

覆盖 data-model §3 四路径（UNIQUE 冲突回查因依赖真实 DB 放 integration）：
  1. 已绑定（oauth_accounts 命中）→ 复用 user_id，刷新 profile
  2. 邮箱命中 → 绑定到既有 user
  3. 全新 → 建 user（password_hash None）+ oauth_accounts
另测 bind_to_user（已登录绑定，409 若已绑他人）+ unbind 安全检查（最后一个登录方式 409）。
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from orchestrator.models.oauth_account import OAuthAccount
from orchestrator.models.user import User
from orchestrator.services.oauth_linker import (
    bind_to_user, link_or_create_user, unbind,
)
from orchestrator.services.oauth_provider import UserInfo


def _userinfo(provider="github", pid="12345", email="alice@example.com") -> UserInfo:
    return UserInfo(
        provider=provider, provider_user_id=pid, email=email,
        display_name="Alice", avatar_url="https://a", raw={"login": "alice"},
    )


def _fake_session() -> MagicMock:
    """构造 mock AsyncSession：scalar/get/add/commit/refresh/execute 全 AsyncMock。"""
    s = MagicMock()
    s.scalar = AsyncMock()
    s.get = AsyncMock()
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.refresh = AsyncMock()
    s.flush = AsyncMock()
    s.rollback = AsyncMock()
    s.execute = AsyncMock()
    s.delete = AsyncMock()
    return s


def _make_user(uid=None, email="alice@example.com", pw_hash="h") -> User:
    return User(id=uid or uuid.uuid4(), email=email, password_hash=pw_hash)


# ---------- 路径 1：已绑定 → 复用 ----------

@pytest.mark.asyncio
async def test_link_or_create_already_bound_reuses_user():
    s = _fake_session()
    existing_user = _make_user()
    existing_oa = OAuthAccount(
        provider="github", provider_user_id="12345", user_id=existing_user.id,
        email="alice@example.com",
    )
    # 第一次 scalar（查 oauth_accounts）返回已绑定记录
    s.scalar.return_value = existing_oa
    s.get.return_value = existing_user

    user = await link_or_create_user(s, _userinfo())

    assert user.id == existing_user.id
    # 不应再建新 user
    assert s.add.call_count == 0
    s.commit.assert_awaited()


# ---------- 路径 2：邮箱命中 → 绑定既有 user ----------

@pytest.mark.asyncio
async def test_link_or_create_email_hit_binds_to_existing():
    s = _fake_session()
    existing_user = _make_user(email="alice@example.com")
    # 第 1 次 scalar（oauth_accounts）→ None；第 2 次（users by email）→ existing_user
    s.scalar.side_effect = [None, existing_user]

    user = await link_or_create_user(s, _userinfo())

    assert user.id == existing_user.id
    # 应新建一条 oauth_accounts（s.add 调用一次）
    assert s.add.call_count == 1
    added = s.add.call_args[0][0]
    assert isinstance(added, OAuthAccount)
    assert added.provider == "github"
    assert added.user_id == existing_user.id
    # 邮箱命中时应刷新 display_name/avatar
    assert existing_user.display_name == "Alice"


# ---------- 路径 3：全新 → 建户（password_hash None）----------

@pytest.mark.asyncio
async def test_link_or_create_brand_new_user_password_hash_none():
    s = _fake_session()
    # oauth_accounts 查空，users 查空
    s.scalar.side_effect = [None, None]

    user = await link_or_create_user(s, _userinfo(email="new@example.com"))

    # 建了 User + OAuthAccount 两条
    assert s.add.call_count == 2
    added_objs = [c[0][0] for c in s.add.call_args_list]
    new_user = next(o for o in added_objs if isinstance(o, User))
    new_oa = next(o for o in added_objs if isinstance(o, OAuthAccount))
    assert new_user.email == "new@example.com"
    # OAuth-only user 无密码：password_hash 存空串哨兵（NOT NULL 约束保持，零迁移；
    # bcrypt verify 永远失败 = 无法密码登录，语义等价 data-model §2.2 的 NULL）
    assert new_user.password_hash == ""
    assert new_user.display_name == "Alice"
    assert new_oa.provider == "github"


@pytest.mark.asyncio
async def test_link_or_create_email_normalized_lower():
    """email 合并按 LOWER()，大写 email 应命中小写 user。"""
    s = _fake_session()
    existing = _make_user(email="alice@example.com")
    s.scalar.side_effect = [None, existing]
    user = await link_or_create_user(s, _userinfo(email="Alice@Example.com"))
    assert user.id == existing.id


# ---------- bind_to_user（已登录绑定）----------

@pytest.mark.asyncio
async def test_bind_to_user_success():
    s = _fake_session()
    current = _make_user()
    s.scalar.return_value = None  # 该 (provider,pid) 未被绑
    await bind_to_user(s, current, _userinfo())
    assert s.add.call_count == 1
    added = s.add.call_args[0][0]
    assert added.user_id == current.id


@pytest.mark.asyncio
async def test_bind_to_user_already_bound_to_other_raises_409():
    s = _fake_session()
    current = _make_user()
    other = _make_user()
    existing_oa = OAuthAccount(provider="github", provider_user_id="12345", user_id=other.id)
    s.scalar.return_value = existing_oa
    import fastapi
    with pytest.raises(fastapi.HTTPException) as exc:
        await bind_to_user(s, current, _userinfo())
    assert exc.value.status_code == 409


# ---------- unbind 安全检查 ----------

@pytest.mark.asyncio
async def test_unbind_refused_when_last_login_method():
    """无 password 且无其他 provider → 409。"""
    s = _fake_session()
    user = _make_user(pw_hash="")  # password_hash 空串（OAuth-only，无密码可登）
    row = OAuthAccount(provider="github", provider_user_id="1", user_id=user.id)
    # 实现顺序：1st scalar=待删记录(row)；2nd scalar=其余 provider 数(0)
    s.scalar.side_effect = [row, 0]
    import fastapi
    with pytest.raises(fastapi.HTTPException) as exc:
        await unbind(s, user, "github")
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_unbind_refused_when_provider_not_bound_404():
    s = _fake_session()
    user = _make_user(pw_hash="hash")
    s.scalar.return_value = None  # 该 provider 未绑定（1st scalar）
    import fastapi
    with pytest.raises(fastapi.HTTPException) as exc:
        await unbind(s, user, "github")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_unbind_success_when_password_exists():
    s = _fake_session()
    user = _make_user(pw_hash="hash")
    row = OAuthAccount(provider="github", provider_user_id="1", user_id=user.id)
    # 1st scalar=待删 row；2nd=其余 provider 数(0)，但有 password，放行
    s.scalar.side_effect = [row, 0]
    await unbind(s, user, "github")
    s.delete.assert_awaited()
