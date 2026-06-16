"""cap-agent 自定义异常。"""
from __future__ import annotations


class CapAgentError(Exception):
    """cap-agent 所有自定义异常的基类。"""


class UpstreamError(CapAgentError):
    """下游服务（cap-terminal/cap-browser）调用失败。"""


class InvalidActionError(CapAgentError):
    """GUI action_type 不在 16 种合法动作内。"""


class TmuxError(CapAgentError):
    """cap-terminal tmux 操作失败。"""
