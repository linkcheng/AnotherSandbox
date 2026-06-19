"""cap-mcp audit_client 测试。research.md R9。"""
import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cap_mcp.services.audit_client import AuditClient


def test_report_no_config_skips():
    AuditClient(orch_url="", workspace_id="").report("fs.write", {}, actor_user_id=None, success=True)


@pytest.mark.asyncio
async def test_report_fires_and_forgets():
    c = AuditClient(orch_url="http://orch:8000", workspace_id="ws-1")
    started = asyncio.Event()

    async def fake_post(self, url, json=None):
        started.set()
        await asyncio.sleep(0.3)
        return httpx.Response(201, json={"id": 1})

    with patch("httpx.AsyncClient.post", new=fake_post):
        c.report("fs.write", {"path": "/x", "bytes": 1}, actor_user_id=None, success=True)
        await asyncio.wait_for(started.wait(), timeout=1.0)
        await asyncio.sleep(0.4)


@pytest.mark.asyncio
async def test_report_swallows_errors(caplog):
    c = AuditClient(orch_url="http://orch:8000", workspace_id="ws-1")
    with patch("httpx.AsyncClient.post", new=AsyncMock(side_effect=httpx.ConnectError("refused"))):
        c.report("browser.action", {}, actor_user_id=None, success=False)
        await asyncio.sleep(0.1)
    assert any("audit report failed" in r.message for r in caplog.records if r.levelname == "WARNING")
