"""审计 schema。contracts/audit-ingest.md。"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditIngestIn(BaseModel):
    workspace_id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    event_type: str
    source: str
    detail: dict
    success: bool


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workspace_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    event_type: str
    source: str
    detail: dict
    success: bool
    created_at: datetime
