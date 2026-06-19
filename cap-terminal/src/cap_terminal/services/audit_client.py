"""cap-terminal 审计上报（fire-and-forget，复用 cap-agent 模式）。

contracts/audit-ingest.md, research.md R9。读 env ORCHESTRATOR_URL/WORKSPACE_ID
（docker-compose.workspace.yml.tmpl 注入），未配置则静默跳过。
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger("cap_terminal.audit")


class AuditClient:
    def __init__(
        self,
        orch_url: str | None = None,
        workspace_id: str | None = None,
        source: str = "cap-terminal",
        timeout: float = 2.0,
    ):
        self.orch_url = orch_url or os.environ.get("ORCHESTRATOR_URL", "")
        self.workspace_id = workspace_id or os.environ.get("WORKSPACE_ID", "")
        self.source = source
        self.timeout = timeout

    def report(self, event_type: str, detail: dict, *, actor_user_id: str | None, success: bool) -> None:
        if not self.orch_url or not self.workspace_id:
            return
        try:
            asyncio.get_running_loop().create_task(self._send(event_type, detail, actor_user_id, success))
        except RuntimeError:
            logger.debug("audit report skipped: no running event loop")

    async def _send(self, event_type: str, detail: dict, actor: str | None, success: bool) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(
                    f"{self.orch_url}/api/v1/audit/ingest",
                    json={
                        "workspace_id": self.workspace_id, "actor_user_id": actor,
                        "event_type": event_type, "source": self.source,
                        "detail": detail, "success": success,
                    },
                )
        except Exception as e:
            logger.warning("audit report failed (best-effort, ignored): %s", e)


audit_client = AuditClient()
