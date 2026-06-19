"""T010: OAuthAccount ORM 结构/约束单测（纯 import + 属性断言，不依赖 DB）。

data-model.md §2.1。FR-003。
"""
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from orchestrator.models.oauth_account import OAuthAccount


def _col(model, name):
    return model.__table__.c[name]


def test_table_name_and_primary_key():
    assert OAuthAccount.__tablename__ == "oauth_accounts"
    pk = _col(OAuthAccount, "id").primary_key
    assert pk is True


def test_provider_check_constraint():
    """provider 仅允许 github/google（CHECK）。"""
    checks = [c for c in OAuthAccount.__table__.constraints if isinstance(c, CheckConstraint)]
    assert any("provider IN" in str(c.sqltext) for c in checks)


def test_provider_user_unique_constraint():
    """(provider, provider_user_id) 全局唯一，防重复绑定。R2。"""
    uniqs = [c for c in OAuthAccount.__table__.constraints if isinstance(c, UniqueConstraint)]
    colnames = [tuple(sorted(c.columns.keys())) for c in uniqs]
    assert ("provider", "provider_user_id") in colnames


def test_user_id_fk_cascade():
    col = _col(OAuthAccount, "user_id")
    assert col.nullable is False
    assert col.index is True  # 反查某 user 的所有 provider
    fks = list(col.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.column.table.name == "users"
    # ondelete CASCADE
    assert fk.ondelete == "CASCADE"


def test_field_types_and_nullability():
    assert isinstance(_col(OAuthAccount, "id").type, UUID)
    assert _col(OAuthAccount, "provider").nullable is False
    assert _col(OAuthAccount, "provider_user_id").nullable is False
    # email 可空（合并锚点）
    assert _col(OAuthAccount, "email").nullable is True
    # raw_profile JSONB 可空
    assert _col(OAuthAccount, "raw_profile").nullable is True
    assert isinstance(_col(OAuthAccount, "raw_profile").type, JSONB)
    # created_at 不可空
    assert _col(OAuthAccount, "created_at").nullable is False


def test_provider_email_index_present():
    """(provider, email) 复合索引用于邮箱合并候选定位。data-model §2.1。"""
    idx_cols = []
    for idx in OAuthAccount.__table__.indexes:
        idx_cols.append(tuple(idx.columns.keys()))
    assert ("provider", "email") in idx_cols


def test_construct_instance_smoke():
    """构造实例无异常，id 可显式传入。"""
    uid = uuid.uuid4()
    oa = OAuthAccount(
        provider="github", provider_user_id="123", user_id=uid,
        email="a@b.c", raw_profile={"login": "a"},
    )
    assert oa.provider == "github"
    assert oa.user_id == uid
