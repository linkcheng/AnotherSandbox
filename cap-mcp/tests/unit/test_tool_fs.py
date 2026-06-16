"""cap-mcp fs_* 工具单元测试。

对应 spec.md FR-027；tasks.md T065；contracts/cap-mcp-tools.md。
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """临时 workspace 目录，重写 WORKSPACE_ROOT。"""
    ws = tmp_path / "workspace"
    ws.mkdir()
    # fs 模块每次调用都读环境变量决定 workspace 根
    monkeypatch.setenv("CAP_MCP_WORKSPACE_ROOT", str(ws))
    return ws


@pytest.mark.asyncio
async def test_fs_write_creates_file(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_write

    result = await fs_write("/workspace/note.md", "hi")
    assert result["ok"] is True
    assert result["bytes"] == 2
    assert (workspace / "note.md").read_text() == "hi"


@pytest.mark.asyncio
async def test_fs_read_returns_content(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_read, fs_write

    await fs_write("/workspace/test.txt", "content")
    result = await fs_read("/workspace/test.txt")
    assert result["ok"] is True
    assert result["content"] == "content"
    assert result["bytes"] == 7


@pytest.mark.asyncio
async def test_fs_read_missing_file_returns_error(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_read

    result = await fs_read("/workspace/nonexistent.txt")
    assert result["ok"] is False
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_fs_write_rejects_path_outside_workspace(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_write

    result = await fs_write("/etc/passwd", "hacked")
    assert result["ok"] is False
    assert "outside" in result["error"].lower()


@pytest.mark.asyncio
async def test_fs_write_rejects_dotdot_traversal(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_write

    result = await fs_write("/workspace/../etc/evil", "x")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_fs_list_returns_entries(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_list, fs_write

    await fs_write("/workspace/a.txt", "a")
    await fs_write("/workspace/b.txt", "bb")
    (workspace / "subdir").mkdir()
    result = await fs_list("/workspace")
    assert result["ok"] is True
    names = sorted(e["name"] for e in result["entries"])
    assert names == ["a.txt", "b.txt", "subdir"]


@pytest.mark.asyncio
async def test_fs_list_entries_have_type_field(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_list, fs_write

    await fs_write("/workspace/x.txt", "x")
    (workspace / "d").mkdir()
    result = await fs_list("/workspace")
    types = {e["name"]: e["type"] for e in result["entries"]}
    assert types["x.txt"] == "file"
    assert types["d"] == "dir"


@pytest.mark.asyncio
async def test_fs_search_finds_pattern(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_search, fs_write

    await fs_write("/workspace/a.txt", "hello\nworld\nhello again")
    result = await fs_search("hello", "/workspace")
    assert result["ok"] is True
    assert len(result["matches"]) >= 2  # 两个 hello


@pytest.mark.asyncio
async def test_fs_search_returns_path_line_text(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_search, fs_write

    await fs_write("/workspace/a.txt", "target line")
    result = await fs_search("target", "/workspace")
    match = result["matches"][0]
    assert "path" in match
    assert "line" in match
    assert match["line"] == 1
    assert "target" in match["text"]


@pytest.mark.asyncio
async def test_fs_search_no_matches_returns_empty(workspace: Path) -> None:
    from cap_mcp.tools.fs import fs_search

    result = await fs_search("nonexistent_pattern", "/workspace")
    assert result["ok"] is True
    assert result["matches"] == []
