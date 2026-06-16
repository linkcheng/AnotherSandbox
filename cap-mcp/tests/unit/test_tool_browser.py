"""cap-mcp browser_* 工具单元测试。

对应 spec.md FR-019、FR-027、FR-028；tasks.md T059；contracts/cap-mcp-tools.md。

实现采用 playwright async_api；mock 入口为 `_get_playwright`，返回
playwright 实例，其 `chromium.connect_over_cdp` 是 AsyncMock 返回 browser。
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_mock_playwright() -> MagicMock:
    """构造 playwright + browser + context + page 的 mock 链。

    - playwright.chromium.connect_over_cdp(...) -> AsyncMock 返回 browser
    - browser.contexts[0].pages[0] -> page
    - page.url, page.title() (AsyncMock), page.goto (AsyncMock),
      page.locator(sel).click/fill (AsyncMock), page.inner_text (AsyncMock),
      page.screenshot (AsyncMock)
    """
    page = MagicMock(name="page")
    page.url = "https://example.com"
    page.title = AsyncMock(return_value="Example Domain")
    page.goto = AsyncMock(return_value=None)
    page.inner_text = AsyncMock(return_value="page body text")
    page.screenshot = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n")

    # locator(sel) 返回对象，其 click/fill 都是 AsyncMock
    locator = MagicMock(name="locator")
    locator.click = AsyncMock(return_value=None)
    locator.fill = AsyncMock(return_value=None)
    page.locator = MagicMock(return_value=locator)

    ctx = MagicMock(name="context")
    ctx.pages = [page]
    ctx.new_page = MagicMock(return_value=page)

    browser = MagicMock(name="browser")
    browser.contexts = [ctx]
    browser.new_context = MagicMock(return_value=ctx)
    browser.close = AsyncMock()

    chromium = MagicMock(name="chromium")
    chromium.connect_over_cdp = AsyncMock(return_value=browser)

    playwright = MagicMock(name="playwright")
    playwright.chromium = chromium
    playwright.stop = AsyncMock()
    return playwright


@pytest.fixture
def mock_playwright() -> MagicMock:
    return _make_mock_playwright()


@pytest.mark.asyncio
async def test_browser_navigate_returns_url_and_title(mock_playwright: MagicMock) -> None:
    from cap_mcp.tools.browser import browser_navigate

    with patch("cap_mcp.tools.browser._get_playwright", new=AsyncMock(return_value=mock_playwright)):
        result = await browser_navigate("https://example.com")
    assert result["ok"] is True
    assert result["url"] == "https://example.com"
    assert result["title"] == "Example Domain"


@pytest.mark.asyncio
async def test_browser_navigate_calls_goto(mock_playwright: MagicMock) -> None:
    from cap_mcp.tools.browser import browser_navigate

    with patch("cap_mcp.tools.browser._get_playwright", new=AsyncMock(return_value=mock_playwright)):
        await browser_navigate("https://example.com")
    page = mock_playwright.chromium.connect_over_cdp.return_value.contexts[0].pages[0]
    page.goto.assert_called_once()
    # 第一个位置参数应为 url
    args, _ = page.goto.call_args
    assert args[0] == "https://example.com"


@pytest.mark.asyncio
async def test_browser_navigate_connection_failure_returns_error(mock_playwright: MagicMock) -> None:
    from cap_mcp.tools.browser import browser_navigate

    mock_playwright.chromium.connect_over_cdp.side_effect = RuntimeError("CDP refused")
    with patch("cap_mcp.tools.browser._get_playwright", new=AsyncMock(return_value=mock_playwright)):
        result = await browser_navigate("https://example.com")
    assert result["ok"] is False
    assert "error" in result
    assert "CDP refused" in result["error"]


@pytest.mark.asyncio
async def test_browser_click_calls_locator(mock_playwright: MagicMock) -> None:
    from cap_mcp.tools.browser import browser_click

    with patch("cap_mcp.tools.browser._get_playwright", new=AsyncMock(return_value=mock_playwright)):
        result = await browser_click("button#submit")
    assert result["ok"] is True
    page = mock_playwright.chromium.connect_over_cdp.return_value.contexts[0].pages[0]
    page.locator.assert_called_with("button#submit")
    page.locator.return_value.click.assert_awaited_once()


@pytest.mark.asyncio
async def test_browser_type_calls_fill(mock_playwright: MagicMock) -> None:
    from cap_mcp.tools.browser import browser_type

    with patch("cap_mcp.tools.browser._get_playwright", new=AsyncMock(return_value=mock_playwright)):
        result = await browser_type("input#name", "hello")
    assert result["ok"] is True
    page = mock_playwright.chromium.connect_over_cdp.return_value.contexts[0].pages[0]
    page.locator.assert_called_with("input#name")
    # fill 第一位置参数应为 text（timeout 等附加 kwargs 允许）
    page.locator.return_value.fill.assert_awaited_once()
    fill_args, _ = page.locator.return_value.fill.await_args
    assert fill_args[0] == "hello"


@pytest.mark.asyncio
async def test_browser_snapshot_returns_url_title_text(mock_playwright: MagicMock) -> None:
    from cap_mcp.tools.browser import browser_snapshot

    page = mock_playwright.chromium.connect_over_cdp.return_value.contexts[0].pages[0]
    page.inner_text = AsyncMock(return_value="page body text")
    with patch("cap_mcp.tools.browser._get_playwright", new=AsyncMock(return_value=mock_playwright)):
        result = await browser_snapshot()
    assert result["url"] == "https://example.com"
    assert result["title"] == "Example Domain"
    assert "page body text" in result["text"]


@pytest.mark.asyncio
async def test_browser_snapshot_truncates_to_4kb(mock_playwright: MagicMock) -> None:
    from cap_mcp.tools.browser import browser_snapshot

    page = mock_playwright.chromium.connect_over_cdp.return_value.contexts[0].pages[0]
    page.inner_text = AsyncMock(return_value="x" * 10000)
    with patch("cap_mcp.tools.browser._get_playwright", new=AsyncMock(return_value=mock_playwright)):
        result = await browser_snapshot()
    assert len(result["text"]) <= 4096


@pytest.mark.asyncio
async def test_browser_screenshot_saves_to_default_path(
    mock_playwright: MagicMock, tmp_path: Path
) -> None:
    from cap_mcp.tools.browser import browser_screenshot

    page = mock_playwright.chromium.connect_over_cdp.return_value.contexts[0].pages[0]
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    def fake_screenshot(*args, **kwargs):
        path = kwargs.get("path")
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(png_bytes)
        return png_bytes

    page.screenshot = AsyncMock(side_effect=fake_screenshot)
    custom_path = str(tmp_path / "subdir" / "shot.png")
    with patch("cap_mcp.tools.browser._get_playwright", new=AsyncMock(return_value=mock_playwright)):
        result = await browser_screenshot(custom_path)
    assert result["ok"] is True
    assert result["bytes"] == len(png_bytes)
    assert result["path"] == custom_path
    assert Path(custom_path).exists()


@pytest.mark.asyncio
async def test_browser_screenshot_default_path_in_shared(
    mock_playwright: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """默认路径 /workspace/shared/screenshot.png 时正确写入并返回 bytes。"""
    from cap_mcp.tools.browser import browser_screenshot

    # 把默认 /workspace 重定向到 tmp_path
    monkeypatch.setenv("CAP_MCP_WORKSPACE_ROOT", str(tmp_path))
    page = mock_playwright.chromium.connect_over_cdp.return_value.contexts[0].pages[0]
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50

    captured: dict[str, str] = {}

    def fake_screenshot(*args, **kwargs):
        path = kwargs.get("path")
        captured["path"] = path
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(png_bytes)
        return png_bytes

    page.screenshot = AsyncMock(side_effect=fake_screenshot)
    with patch("cap_mcp.tools.browser._get_playwright", new=AsyncMock(return_value=mock_playwright)):
        result = await browser_screenshot()
    assert result["ok"] is True
    assert result["bytes"] == len(png_bytes)
    # 截图实际落盘
    assert Path(captured["path"]).exists()
