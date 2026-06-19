"""WorkspaceOwner ORM（data-model.md §2.4，复合 PK + role）。"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from orchestrator.models.base import Base


class WorkspaceOwner(Base):
    __tablename__ = "workspace_owners"
    __table_args__ = (
        CheckConstraint("role IN ('owner','collaborator','viewer')", name="ck_wo_role"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
