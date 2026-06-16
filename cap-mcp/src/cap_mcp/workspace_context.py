"""cap-mcp workspace 上下文加载器。

首次收到 MCP 请求时读取 /workspace/AGENTS.md（或降级 README.md），
附加顶层目录列表作为 system prompt 上下文。
对应 spec.md FR-013、设计原则四。
"""
from __future__ import annotations

import os
from pathlib import Path

_cache: str | None = None


def _workspace_root() -> Path:
    """运行时读环境变量，便于测试 monkeypatch。"""
    return Path(os.getenv("CAP_MCP_WORKSPACE_ROOT", "/workspace"))


def reset_cache() -> None:
    """清空 cache（测试用）。"""
    global _cache
    _cache = None


def _read_first_lines(path: Path, max_chars: int = 4096) -> str:
    """读取文件前 max_chars 字符。"""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return content[:max_chars]


def _list_top_level(root: Path, limit: int = 30) -> str:
    """列出 workspace 顶层目录（最多 limit 项）。"""
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name)
    except OSError:
        return ""
    lines: list[str] = []
    for entry in entries[:limit]:
        kind = "dir" if entry.is_dir() else "file"
        lines.append(f"- {entry.name} ({kind})")
    return "\n\n".join(lines) if not lines else "\n".join(lines)


async def load_workspace_context() -> str:
    """加载 workspace 上下文文本（懒加载 + cache，async 版本）。

    优先级：AGENTS.md > README.md > 仅目录列表。

    Returns:
        拼接好的上下文字符串。
    """
    return load_workspace_context_sync()


def load_workspace_context_sync() -> str:
    """加载 workspace 上下文（同步版本，供 FastMCP 构造时调用）。"""
    global _cache
    if _cache is not None:
        return _cache

    root = _workspace_root()
    parts: list[str] = []

    agents_md = root / "AGENTS.md"
    readme_md = root / "README.md"

    if agents_md.exists():
        content = _read_first_lines(agents_md)
        if content:
            parts.append(f"# AGENTS.md\n\n{content}")
    elif readme_md.exists():
        content = _read_first_lines(readme_md)
        if content:
            parts.append(f"# README.md\n\n{content}")

    listing = _list_top_level(root)
    if listing:
        parts.append(f"# Workspace 顶层目录\n\n{listing}")

    _cache = "\n\n".join(parts) if parts else "(workspace empty)"
    return _cache
