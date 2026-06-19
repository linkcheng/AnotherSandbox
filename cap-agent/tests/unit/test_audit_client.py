"""T060: cap-agent audit_client 测试（fire-and-forget + best-effort）。research.md R9。"""
import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cap_agent.services.audit_client import AuditClient


def test_report_no_config_skips_silently():
    c = AuditClient(orch_url="", workspace_id="", source="cap-agent")
    # 不应抛异常
    c.report("gui.action", {"x": 1}, actor_user_id="u", success=True)


@pytest.mark.asyncio
async def test_report_fires_and_forgets_not_blocking_caller():
    c = AuditClient(orch_url="http://orch:8000", workspace_id="ws-1", source="cap-agent")
    started = asyncio.Event()

    async def fake_post(self, url, json=None):
        started.set()
        # 模拟慢响应
        await asyncio.sleep(0.5)
        return httpx.Response(201, json={"id": 1})

    with patch("httpx.AsyncClient.post", new=fake_post):
        # report 应立即返回（不 await 慢响应）
        loop = asyncio.get_running_loop()
        c.report("gui.action", {"action_type": "click"}, actor_user_id="u", success=True)
        # create_task 已派发，report 已返回（无 await）
        # 等待后台任务执行 fake_post
        await asyncio.wait_for(started.wait(), timeout=1.0)
        # 让后台任务完成
        await asyncio.sleep(0.6)


@pytest.mark.asyncio
async def test_report_swallows_errors_best_effort(caplog):
    c = AuditClient(orch_url="http://orch:8000", workspace_id="ws-1", source="cap-agent")
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.ConnectError("refused"))):
        c.report("gui.action", {}, actor_user_id=None, success=False)
        # 让后台任务跑完（吞异常）
        await asyncio.sleep(0.1)
    # 不应有未捕获异常；warning 被记录
    assert any("audit report failed" in r.message for r in caplog.records if r.levelname == "WARNING")
