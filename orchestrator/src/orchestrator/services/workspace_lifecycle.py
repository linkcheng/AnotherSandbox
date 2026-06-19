"""Workspace 状态机 + slug/volume 生成。§8.5, data-model.md §6, research.md R1。"""
import re
import secrets

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
