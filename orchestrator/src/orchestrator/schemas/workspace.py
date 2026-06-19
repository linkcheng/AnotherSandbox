"""Workspace schema。contracts/orchestrator-rest-api §2。"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkspaceCreateIn(BaseModel):
    name: str
    template: str | None = None


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name: str
    status: str
    external_port: int
    compose_project: str
    created_at: datetime
    endpoints: dict[str, str] | None = None
