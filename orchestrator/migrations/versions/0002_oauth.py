"""oauth: oauth_accounts 表 + users 增 display_name/avatar_url

Revision ID: 0002_oauth
Revises: 0001_init
Create Date: 2026-06-20

零迁移扩展：P2 既有 6 表结构不变。data-model.md §4。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0002_oauth"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) oauth_accounts 表（data-model.md §2.1）
    op.create_table(
        "oauth_accounts",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_user_id", sa.Text, nullable=False),
        sa.Column(
            "user_id", UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("raw_profile", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("provider IN ('github', 'google')", name="ck_oauth_provider"),
    )
    # 唯一约束：同 provider 同外部账号全局唯一（防重复绑定，R2）
    op.create_unique_constraint(
        "uq_oauth_provider_user", "oauth_accounts", ["provider", "provider_user_id"],
    )
    # 索引：user_id 反查某 user 绑定的所有 provider
    op.create_index("ix_oauth_accounts_user_id", "oauth_accounts", ["user_id"])
    # 复合索引：OAuth 回调按 provider+email 定位邮箱合并候选（R2）
    op.create_index("ix_oauth_provider_email", "oauth_accounts", ["provider", "email"])

    # 2) users 增列 display_name / avatar_url（nullable，data-model.md §2.2）
    op.add_column("users", sa.Column("display_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(512), nullable=True))


def downgrade() -> None:
    # 逆序：先撤 users 增列，再删 oauth_accounts
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "display_name")
    op.drop_index("ix_oauth_provider_email", table_name="oauth_accounts")
    op.drop_index("ix_oauth_accounts_user_id", table_name="oauth_accounts")
    op.drop_table("oauth_accounts")
