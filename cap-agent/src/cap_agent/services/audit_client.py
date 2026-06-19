"""cap-agent 审计上报（fire-and-forget，best-effort）。contracts/audit-ingest.md §4/5, research.md R9。"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger("cap_agent.audit")


class AuditClient:
    """上报审计事件；绝不阻塞业务路径（create_task + 超时丢弃）。"""

    def __init__(
        self,
        orch_url: str | None = None,
        workspace_id: str | None = None,
        source: str = "cap-agent",
        timeout: float = 2.0,
    ):
        self.orch_url = orch_url or os.environ.get("ORCHESTRATOR_URL", "")
        self.workspace_id = workspace_id or os.environ.get("WORKSPACE_ID", "")
        self.source = source
        self.timeout = timeout

    def report(
        self, event_type: str, detail: dict, *, actor_user_id: str | None, success: bool
    ) -> None:
        """同步触发，异步上报；调用方不感知成功/失败。"""
        if not self.orch_url or not self.workspace_id:
            return  # 未配置（P1 或无 Orchestrator）→ 静默跳过
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._send(event_type, detail, actor_user_id, success))
        except RuntimeError:
            # 无运行中 loop（同步上下文）→ 丢弃，不阻塞
            logger.debug("audit report skipped: no running event loop")

    async def _send(self, event_type: str, detail: dict, actor: str | None, success: bool) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(
                    f"{self.orch_url}/api/v1/audit/ingest",
                    json={
                        "workspace_id": self.workspace_id,
                        "actor_user_id": actor,
                        "event_type": event_type,
                        "source": self.source,
                        "detail": detail,
                        "success": success,
                    },
                )
        except Exception as e:  # best-effort：超时/拒绝/5xx 全吞
            logger.warning("audit report failed (best-effort, ignored): %s", e)
