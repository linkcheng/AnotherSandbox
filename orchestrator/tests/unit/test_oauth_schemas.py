"""T013: OAuth schemas 单测。data-model §2.1, contracts/oauth-rest-api §3。"""
import uuid
from datetime import datetime, timezone

from orchestrator.schemas.auth import UserOut
from orchestrator.schemas.oauth import (
    MeOut, OAuthAccountOut, OAuthAccountsResponse,
)


def test_oauth_account_out_from_attributes():
    """OAuthAccountOut 从 ORM 属性构造。"""
    class FakeOA:
        provider = "github"
        email = "alice@example.com"
        created_at = datetime(2026, 6, 20, 4, 0, tzinfo=timezone.utc)
    out = OAuthAccountOut.model_validate(FakeOA())
    assert out.provider == "github"
    assert out.email == "alice@example.com"


def test_oauth_accounts_response_shape():
    r = OAuthAccountsResponse(accounts=[
        OAuthAccountOut(provider="github", email="a@b.c", created_at=datetime.now(timezone.utc)),
    ])
    assert len(r.accounts) == 1
    assert r.accounts[0].provider == "github"


def test_me_out_includes_oauth_fields():
    """MeOut 含 display_name/avatar_url，用于 /me。"""
    uid = uuid.uuid4()
    m = MeOut(
        id=uid, email="a@b.c", display_name="Alice", avatar_url="https://x/a.png",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert m.display_name == "Alice"
    assert m.avatar_url == "https://x/a.png"


def test_me_out_from_attributes_user_orm_like():
    """MeOut 能从 User ORM 实例（含 display_name/avatar_url）构造。"""
    class FakeUser:
        id = uuid.uuid4()
        email = "x@y.z"
        display_name = None
        avatar_url = None
        created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    m = MeOut.model_validate(FakeUser())
    assert m.display_name is None
    assert m.email == "x@y.z"


def test_user_out_unchanged_backward_compat():
    """P2 UserOut 既有字段不变（零迁移）。"""
    u = UserOut(id=uuid.uuid4(), email="a@b.c", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert u.id and u.email == "a@b.c"
