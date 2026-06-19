"""Workspace 状态机 + slug/volume 生成。§8.5, data-model.md §6, research.md R1。"""
import re
import secrets

from orchestrator.services.compose_runner import ComposeResult

# 合法动作 → 允许的前置状态
_TRANSITIONS: dict[str, set[str]] = {
    "start": {"created", "stopped"},
    "stop": {"running", "paused", "starting"},
    "pause": {"running"},
    "resume": {"paused"},
    "delete": {"created", "running", "paused", "stopped", "error"},
}
_TARGET: dict[str, str] = {
    "start": "running", "stop": "stopped", "pause": "paused", "resume": "running", "delete": "deleted",
}

# error_message 截断上限（防前端展示失控；TEXT 列无硬限）
_ERROR_MESSAGE_MAX = 2000


def make_slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "ws"
    return f"{base}-{secrets.token_hex(3)}"


def validate_transition(action: str, current: str) -> str:
    """返回目标状态。已在目标态 → 幂等返回；非法转换 raise ValueError。"""
    if action not in _TRANSITIONS:
        raise ValueError(f"unknown action: {action}")
    target = _TARGET[action]
    if current == target:
        return current  # 幂等
    if current not in _TRANSITIONS[action]:
        raise ValueError(f"illegal transition: {action} from {current}")
    return target


def volume_path(root: str, slug: str) -> str:
    return f"{root}/{slug}"


def apply_start_result(ws, result: ComposeResult) -> None:
    """将 compose up 结果应用到 workspace（FR-018）。

    成功 → status=running + 清空 error_message（避免历史错误残留误导用户）。
    失败 → status=error + error_message 记 stderr 摘要（截断防失控）。

    compose_runner 零改动（FR-019）：本函数仅消费其 ComposeResult，不感知子进程细节。
    调用方（workspaces.start_workspace）负责 commit。
    """
    if result.success:
        ws.status = "running"
        ws.error_message = None
        return
    # 失败：转 error 态，保留 stderr 摘要供前端展示与排障
    ws.status = "error"
    stderr = (result.stderr or "").strip()
    if not stderr:
        # stderr 空也写非空占位，便于前端判定「有错误」而非「无错误字段」
        ws.error_message = f"compose up failed (returncode={result.returncode})"
    else:
        ws.error_message = stderr[:_ERROR_MESSAGE_MAX]
