"""workspace_error: workspaces 增 error_message 列（FR-018）

Revision ID: 0003_workspace_error
Revises: 0002_oauth
Create Date: 2026-06-20

零迁移扩展：P2/P3 既有表结构不变，仅 workspaces 增 nullable Text 列。
启动失败时记录 compose stderr 摘要，供前端展示与排障。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_workspace_error"
down_revision: Union[str, None] = "0002_oauth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # workspaces 增 error_message（nullable Text，FR-018）
    op.add_column("workspaces", sa.Column("error_message", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("workspaces", "error_message")
