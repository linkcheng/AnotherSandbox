"""Workspace ORM（data-model.md §2.3, research.md R2 partial unique）。

datetime 字段显式 DateTime(timezone=True)，与 migration TIMESTAMPTZ 对齐
（避免 asyncpg offset-naive/aware 冲突）。
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from orchestrator.models.base import Base


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint(
            "status IN ('created','starting','running','paused','stopped','deleted','error')",
            name="ck_workspaces_status",
        ),
        Index(
            "uq_workspaces_external_port_active",
            "external_port",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="created", server_default=text("'created'"))
    compose_project: Mapped[str] = mapped_column(String(64), nullable=False)
    external_port: Mapped[int] = mapped_column(Integer, nullable=False)
    volume_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
