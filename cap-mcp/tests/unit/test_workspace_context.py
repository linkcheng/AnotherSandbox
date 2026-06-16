"""cap-mcp workspace_context 单元测试。

对应 spec.md FR-013；tasks.md T082。
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """临时 workspace 目录。"""
    ws = tmp_path / "workspace"
    ws.mkdir()
    monkeypatch.setenv("CAP_MCP_WORKSPACE_ROOT", str(ws))
    return ws


@pytest.mark.asyncio
async def test_load_with_agents_md(workspace: Path) -> None:
    """AGENTS.md 存在时优先使用。"""
    from cap_mcp.workspace_context import load_workspace_context, reset_cache

    reset_cache()
    (workspace / "AGENTS.md").write_text("# Project\nThis is project info.", encoding="utf-8")

    ctx = await load_workspace_context()

    assert "# Project" in ctx
    assert "This is project info" in ctx
    reset_cache()


@pytest.mark.asyncio
async def test_load_fallback_to_readme(workspace: Path) -> None:
    """AGENTS.md 缺失时降级 README.md。"""
    from cap_mcp.workspace_context import load_workspace_context, reset_cache

    reset_cache()
    (workspace / "README.md").write_text("# Readme\nfallback content", encoding="utf-8")

    ctx = await load_workspace_context()

    assert "# Readme" in ctx
    assert "fallback content" in ctx
    reset_cache()


@pytest.mark.asyncio
async def test_load_agents_md_takes_priority_over_readme(workspace: Path) -> None:
    """同时存在时 AGENTS.md 优先。"""
    from cap_mcp.workspace_context import load_workspace_context, reset_cache

    reset_cache()
    (workspace / "AGENTS.md").write_text("AGENTS_CONTENT", encoding="utf-8")
    (workspace / "README.md").write_text("README_CONTENT", encoding="utf-8")

    ctx = await load_workspace_context()

    assert "AGENTS_CONTENT" in ctx
    assert "README_CONTENT" not in ctx
    reset_cache()


@pytest.mark.asyncio
async def test_load_no_files_returns_directory_listing(workspace: Path) -> None:
    """AGENTS.md 与 README.md 都缺失时返回目录列表。"""
    from cap_mcp.workspace_context import load_workspace_context, reset_cache

    reset_cache()
    (workspace / "code").mkdir()
    (workspace / "code" / "main.py").write_text("print('hi')", encoding="utf-8")
    (workspace / "note.txt").write_text("note", encoding="utf-8")

    ctx = await load_workspace_context()

    # 列出顶层目录或文件
    assert "code" in ctx or "main.py" in ctx
    assert "note.txt" in ctx
    reset_cache()


@pytest.mark.asyncio
async def test_load_cached_after_first_call(workspace: Path) -> None:
    """第二次调用不重新读文件（懒加载 cache）。"""
    from cap_mcp.workspace_context import load_workspace_context, reset_cache

    reset_cache()
    (workspace / "AGENTS.md").write_text("V1", encoding="utf-8")

    ctx1 = await load_workspace_context()
    (workspace / "AGENTS.md").write_text("V2", encoding="utf-8")
    ctx2 = await load_workspace_context()

    assert ctx1 == ctx2  # 第二次读到的还是 V1（cache 命中）
    reset_cache()


@pytest.mark.asyncio
async def test_load_empty_workspace(workspace: Path) -> None:
    """空 workspace 不报错。"""
    from cap_mcp.workspace_context import load_workspace_context, reset_cache

    reset_cache()
    ctx = await load_workspace_context()
    assert isinstance(ctx, str)
    reset_cache()


@pytest.mark.asyncio
async def test_load_includes_top_level_directory_listing(workspace: Path) -> None:
    """AGENTS.md 存在时也附上目录列表（前 30 项）。"""
    from cap_mcp.workspace_context import load_workspace_context, reset_cache

    reset_cache()
    (workspace / "AGENTS.md").write_text("project info", encoding="utf-8")
    (workspace / "code").mkdir()
    (workspace / "shared").mkdir()

    ctx = await load_workspace_context()

    assert "project info" in ctx
    assert "code" in ctx
    assert "shared" in ctx
    reset_cache()
