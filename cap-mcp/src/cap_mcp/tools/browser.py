"""cap-mcp browser_* 工具：playwright 连接 cap-browser:9222 共享 Chromium。

设计原则三：human 与 agent 共享同一 tab 与登录态。所有工具操作
browser.contexts[0].pages[0]（活动 page），保证 agent 操作与 human 浏览器视图一致。

依赖 playwright.async_api。`_get_playwright()` 是可 mock 的入口。
"""
from __future__ import annotations

import os
from typing import Any

from cap_mcp.services.audit_client import audit_client

CDP_ENDPOINT = os.getenv("CAP_MCP_BROWSER_CDP_URL", "http://cap-browser:9222")

# 全局 playwright + browser 连接（懒初始化；测试中通过 patch _get_playwright 替换）
_playwright: Any = None
_browser: Any = None


async def _get_playwright() -> Any:
    """获取已连接 playwright 实例，懒初始化并复用连接。

    返回 playwright 对象；其 `chromium.connect_over_cdp(CDP_ENDPOINT)`
    返回 browser。生产环境保留单一连接；测试通过 patch 此函数注入 mock。
    """
    global _playwright, _browser
    if _playwright is None:
        from playwright.async_api import async_playwright

        _playwright = await async_playwright().start()
    if _browser is None:
        _browser = await _playwright.chromium.connect_over_cdp(CDP_ENDPOINT)
    return _playwright


def _active_page(browser: Any) -> Any:
    """从 browser 选出活动 page：优先 contexts[0].pages[0]，必要时新建。

    playwright BrowserContext 在 CDP 模式下复用 human 的 tab。
    """
    contexts = getattr(browser, "contexts", None) or []
    if not contexts:
        # CDP 连接通常会带入 human 的 context；若空则新建
        ctx = browser.new_context()
        contexts = [ctx]
    ctx = contexts[0]
    pages = getattr(ctx, "pages", None) or []
    if not pages:
        page = ctx.new_page()
        pages = [page]
    return pages[0]


async def browser_navigate(url: str) -> dict[str, Any]:
    """导航到 URL，返回页面 title 与最终 URL。

    Args:
        url: 目标 URL。

    Returns:
        ok=True 时含 url + title；失败含 ok=False + error + url。
    """
    try:
        pw = await _get_playwright()
        browser = await pw.chromium.connect_over_cdp(CDP_ENDPOINT)
        page = _active_page(browser)
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await page.title()
        result = {"ok": True, "url": page.url, "title": title}
        audit_client.report("browser.action", {"action": "navigate", "url": url, "ok": True}, actor_user_id=None, success=True)
        return result
    except Exception as e:  # noqa: BLE001 — 不抛异常让 MCP 客户端处理
        return {"ok": False, "url": url, "title": "", "error": str(e)}


async def browser_click(selector: str) -> dict[str, Any]:
    """点击元素。

    Args:
        selector: CSS / playwright selector。

    Returns:
        ok=True 或 ok=False + error。
    """
    try:
        pw = await _get_playwright()
        browser = await pw.chromium.connect_over_cdp(CDP_ENDPOINT)
        page = _active_page(browser)
        await page.locator(selector).click(timeout=10000)
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


async def browser_type(selector: str, text: str) -> dict[str, Any]:
    """输入文本。

    Args:
        selector: CSS / playwright selector。
        text: 要输入的文本。

    Returns:
        ok=True 或 ok=False + error。
    """
    try:
        pw = await _get_playwright()
        browser = await pw.chromium.connect_over_cdp(CDP_ENDPOINT)
        page = _active_page(browser)
        await page.locator(selector).fill(text, timeout=10000)
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


async def browser_snapshot() -> dict[str, Any]:
    """获取当前页面快照（url + title + 文本前 4KB）。

    Returns:
        含 url + title + text；失败时 ok 缺省但 error 存在。
    """
    try:
        pw = await _get_playwright()
        browser = await pw.chromium.connect_over_cdp(CDP_ENDPOINT)
        page = _active_page(browser)
        text = (await page.inner_text("body"))[:4096]
        title = await page.title()
        return {"url": page.url, "title": title, "text": text}
    except Exception as e:  # noqa: BLE001
        return {"url": "", "title": "", "text": "", "error": str(e)}


async def browser_screenshot(path: str = "/workspace/shared/screenshot.png") -> dict[str, Any]:
    """截图保存到指定路径（默认 /workspace/shared/screenshot.png）。

    Args:
        path: 保存路径；目录不存在自动创建。

    Returns:
        ok=True 时含 path + bytes；失败含 ok=False + error。
    """
    try:
        from pathlib import Path

        # 默认路径受 CAP_MCP_WORKSPACE_ROOT 影响（与 fs 工具一致）
        if path == "/workspace/shared/screenshot.png":
            root = os.getenv("CAP_MCP_WORKSPACE_ROOT", "/workspace")
            path = f"{root.rstrip('/')}/shared/screenshot.png"

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        pw = await _get_playwright()
        browser = await pw.chromium.connect_over_cdp(CDP_ENDPOINT)
        page = _active_page(browser)
        data = await page.screenshot(path=path, full_page=False)
        return {"ok": True, "path": path, "bytes": len(data) if data else 0}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "path": path, "bytes": 0, "error": str(e)}
