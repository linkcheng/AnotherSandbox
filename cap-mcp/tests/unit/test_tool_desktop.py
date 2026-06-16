"""cap-mcp desktop_* 工具单元测试。

对应 spec.md FR-027、FR-028；tasks.md T079；contracts/cap-mcp-tools.md。
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import respx
import pytest

os.environ.setdefault("CAP_MCP_AGENT_URL", "http://cap-agent:9000")


@pytest.mark.asyncio
async def test_desktop_screenshot_calls_agent_and_saves_file(tmp_path: Path) -> None:
    from cap_mcp.tools.desktop import desktop_screenshot

    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 2048
    custom_path = str(tmp_path / "shot.png")

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        mock.get("/gui/screenshot").mock(
            return_value=httpx.Response(
                200, content=fake_png, headers={"content-type": "image/png"}
            )
        )
        result = await desktop_screenshot(custom_path)

    assert result["ok"] is True
    assert result["bytes"] == len(fake_png)
    assert Path(custom_path).read_bytes() == fake_png


@pytest.mark.asyncio
async def test_desktop_screenshot_upstream_error_returns_error_dict(tmp_path: Path) -> None:
    from cap_mcp.tools.desktop import desktop_screenshot

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        mock.get("/gui/screenshot").mock(return_value=httpx.Response(503))
        result = await desktop_screenshot(str(tmp_path / "x.png"))

    assert result["ok"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_desktop_screenshot_connection_failure_returns_error_dict(tmp_path: Path) -> None:
    from cap_mcp.tools.desktop import desktop_screenshot

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        mock.get("/gui/screenshot").mock(side_effect=httpx.ConnectError("refused"))
        result = await desktop_screenshot(str(tmp_path / "x.png"))

    assert result["ok"] is False
    assert "error" in result


@pytest.mark.asyncio
async def test_desktop_click_posts_action_to_agent() -> None:
    from cap_mcp.tools.desktop import desktop_click

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        route = mock.post("/gui/actions").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        result = await desktop_click(100, 200, button="left")

    body = route.calls.last.request.read().decode()
    assert '"action_type":"click"' in body
    assert '"x":100' in body
    assert '"y":200' in body
    assert '"button":"left"' in body
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_desktop_type_posts_typing_action() -> None:
    from cap_mcp.tools.desktop import desktop_type

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        route = mock.post("/gui/actions").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await desktop_type("hello world")

    body = route.calls.last.request.read().decode()
    assert '"action_type":"typing"' in body
    assert "hello world" in body


@pytest.mark.asyncio
async def test_desktop_click_default_button_left() -> None:
    from cap_mcp.tools.desktop import desktop_click

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        route = mock.post("/gui/actions").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        await desktop_click(1, 2)

    body = route.calls.last.request.read().decode()
    assert '"button":"left"' in body


@pytest.mark.asyncio
async def test_desktop_click_upstream_error_returns_error_dict() -> None:
    from cap_mcp.tools.desktop import desktop_click

    with respx.mock(base_url="http://cap-agent:9000") as mock:
        mock.post("/gui/actions").mock(return_value=httpx.Response(500))
        result = await desktop_click(0, 0)

    assert result["ok"] is False
    assert "error" in result
