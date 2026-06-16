"""cap-mcp fs_* 工具：直接读写 /workspace/。

路径必须解析后落在 WORKSPACE_ROOT 内，防穿越。
WORKSPACE_ROOT 每次调用读取，支持配置热更与测试 monkeypatch。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    """读取 workspace 根目录（每次调用读 env）。"""
    return Path(os.getenv("CAP_MCP_WORKSPACE_ROOT", "/workspace")).resolve()


# 虚拟 workspace 挂载点（契约规定用户以 /workspace/... 调用）
_VIRTUAL_PREFIX = "/workspace"


def _resolve_safe(path: str) -> Path | None:
    """解析路径并校验落在 WORKSPACE_ROOT 内。

    映射规则：
    - `/workspace`         → root
    - `/workspace/foo`     → root/foo
    - `foo` 或 `./foo`     → root/foo
    - 其他绝对路径（如 /etc/passwd）或 `/workspace/../etc` → 越界返回 None

    Args:
        path: 用户提供的路径。

    Returns:
        Path 对象（安全）；None（路径越界）。
    """
    root = _workspace_root()
    try:
        p = path.strip()
        if p.startswith(_VIRTUAL_PREFIX + "/") or p == _VIRTUAL_PREFIX:
            rel = p[len(_VIRTUAL_PREFIX):].lstrip("/") or "."
            target = (root / rel).resolve()
        elif p.startswith("/"):
            # 绝对路径但不在 /workspace 下，直接越界
            return None
        else:
            target = (root / p.lstrip("/")).resolve()
    except (OSError, ValueError):
        return None
    # resolve 后必须等于 root 或在 root 下（防 /workspace/../etc）
    if target != root and root not in target.parents:
        return None
    return target


async def fs_read(path: str) -> dict[str, Any]:
    """读取文件内容。

    Args:
        path: 文件路径（workspace 内）。

    Returns:
        ok=True 时含 content + bytes；否则 ok=False + error。
    """
    target = _resolve_safe(path)
    if target is None:
        return {
            "ok": False,
            "error": "path outside workspace",
            "content": "",
            "bytes": 0,
        }
    if not target.exists() or not target.is_file():
        return {
            "ok": False,
            "error": f"not found: {path}",
            "content": "",
            "bytes": 0,
        }
    content = target.read_text(encoding="utf-8")
    return {
        "ok": True,
        "content": content,
        "bytes": len(content.encode("utf-8")),
    }


async def fs_write(path: str, content: str) -> dict[str, Any]:
    """写入文件。

    Args:
        path: 文件路径（workspace 内）。
        content: 文本内容。

    Returns:
        ok=True 时含 bytes；否则 ok=False + error。
    """
    target = _resolve_safe(path)
    if target is None:
        return {"ok": False, "error": "path outside workspace", "bytes": 0}
    target.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    target.write_bytes(data)
    return {"ok": True, "bytes": len(data)}


async def fs_list(path: str = "/workspace") -> dict[str, Any]:
    """列出目录内容。

    Args:
        path: 目录路径（workspace 内），默认 /workspace。

    Returns:
        ok=True 时含 entries 列表（每项 name/type/size）；否则 ok=False + error。
    """
    target = _resolve_safe(path)
    if target is None:
        return {"ok": False, "error": "path outside workspace", "entries": []}
    if not target.exists() or not target.is_dir():
        return {"ok": False, "error": f"not a directory: {path}", "entries": []}
    entries: list[dict[str, Any]] = []
    for child in sorted(target.iterdir()):
        if child.is_dir():
            entries.append({"name": child.name, "type": "dir", "size": 0})
        else:
            entries.append(
                {"name": child.name, "type": "file", "size": child.stat().st_size}
            )
    return {"ok": True, "entries": entries}


async def fs_search(pattern: str, path: str = "/workspace") -> dict[str, Any]:
    """递归搜索文本模式。

    Args:
        pattern: 子串匹配模式。
        path: 搜索根目录（workspace 内），默认 /workspace。

    Returns:
        ok=True 时含 matches 列表（每项 path/line/text）；否则 ok=False + error。
    """
    target = _resolve_safe(path)
    if target is None:
        return {"ok": False, "error": "path outside workspace", "matches": []}
    if not target.exists():
        return {"ok": False, "error": f"not found: {path}", "matches": []}
    root = _workspace_root()
    matches: list[dict[str, Any]] = []
    for file_path in target.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            if pattern in line:
                rel = "/" + str(file_path.relative_to(root))
                matches.append(
                    {"path": rel, "line": lineno, "text": line[:200]}
                )
    return {"ok": True, "matches": matches}
