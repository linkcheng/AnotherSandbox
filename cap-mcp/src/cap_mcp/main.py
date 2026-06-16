"""cap-mcp FastAPI + FastMCP 应用装配。

- FastAPI：承载 /health 端点（docker-compose healthcheck）。
- FastMCP：Streamable HTTP server，挂在 /mcp/sandbox/，暴露 shell_exec 工具。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastmcp import FastMCP

from cap_mcp.routers import health
from cap_mcp.tools.browser import (
    browser_click,
    browser_navigate,
    browser_screenshot,
    browser_snapshot,
    browser_type,
)
from cap_mcp.tools.desktop import desktop_click, desktop_screenshot, desktop_type
from cap_mcp.tools.fs import fs_list, fs_read, fs_search, fs_write
from cap_mcp.tools.shell import shell_exec
from cap_mcp.workspace_context import load_workspace_context_sync

# MCP 工具挂载路径（与 cap-nginx /mcp/sandbox/ 反代对齐）
MCP_PATH = "/mcp/sandbox"


def create_mcp() -> FastMCP:
    """构建 MCP server 实例并注册 shell/fs/browser 工具。"""
    workspace_ctx = load_workspace_context_sync()
    instructions = (
        "AI 个人沙箱 MCP server，暴露 shell/fs/browser/desktop 工具。\n\n"
        f"{workspace_ctx}"
    )
    mcp = FastMCP(
        name="cap-mcp",
        instructions=instructions,
    )

    # --- shell 工具 ---
    mcp.tool(
        name="shell_exec",
        description="执行 shell 命令（共享 tmux session）",
    )(shell_exec)

    # --- fs 工具（FR-027）---
    mcp.tool(name="fs_read", description="读取 /workspace/ 下文件")(fs_read)
    mcp.tool(name="fs_write", description="写入文件到 /workspace/")(fs_write)
    mcp.tool(name="fs_list", description="列出目录内容")(fs_list)
    mcp.tool(name="fs_search", description="递归搜索文本")(fs_search)

    # --- browser 工具（FR-019、FR-028）---
    mcp.tool(name="browser_navigate", description="浏览器导航到 URL")(browser_navigate)
    mcp.tool(name="browser_click", description="点击元素")(browser_click)
    mcp.tool(name="browser_type", description="输入文本到元素")(browser_type)
    mcp.tool(name="browser_snapshot", description="获取页面快照（url/title/text）")(browser_snapshot)
    mcp.tool(name="browser_screenshot", description="截图保存到文件")(browser_screenshot)

    # --- desktop 工具（FR-018、FR-028）---
    mcp.tool(name="desktop_screenshot", description="桌面截图（pyautogui）")(desktop_screenshot)
    mcp.tool(name="desktop_click", description="桌面点击坐标")(desktop_click)
    mcp.tool(name="desktop_type", description="桌面输入文本")(desktop_type)

    return mcp


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：US1 占位，US2/US3 起将初始化 MCP 工具注册与 playwright。"""
    yield


def create_app() -> FastAPI:
    """构建 FastAPI 应用实例并挂载 MCP server。"""
    app = FastAPI(
        title="cap-mcp",
        description="AI 个人沙箱 MCP server",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health.router)

    # 挂载 FastMCP Streamable HTTP server 到 /mcp/sandbox
    mcp = create_mcp()
    app.mount(MCP_PATH, mcp.http_app(transport="streamable-http"))

    return app


# 模块级实例（uvicorn 入口）
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "cap_mcp.main:app",
        host="0.0.0.0",
        port=8940,
        reload=False,
    )
