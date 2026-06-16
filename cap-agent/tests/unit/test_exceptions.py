"""cap-agent 异常体系单元测试。

对应 spec.md、tasks.md T015。
"""
from __future__ import annotations

import pytest

from cap_agent.core.exceptions import (
    CapAgentError,
    InvalidActionError,
    TmuxError,
    UpstreamError,
)


def test_all_subclasses_inherit_from_base() -> None:
    """所有自定义异常必须继承 CapAgentError，便于上层统一捕获。"""
    for exc_cls in (UpstreamError, InvalidActionError, TmuxError):
        assert issubclass(exc_cls, CapAgentError)


def test_each_exception_can_be_raised_and_caught() -> None:
    """三种异常都能 raise 与 except 捕获。"""
    with pytest.raises(UpstreamError, match="503"):
        raise UpstreamError("cap-terminal returned 503")

    with pytest.raises(InvalidActionError, match="invalid_action"):
        raise InvalidActionError("invalid_action_type=invalid_action")

    with pytest.raises(TmuxError, match="session not found"):
        raise TmuxError("session not found: foo")


def test_base_can_catch_all_subclasses() -> None:
    """捕获基类即可兜住所有子类异常。"""
    for exc_cls in (UpstreamError, InvalidActionError, TmuxError):
        with pytest.raises(CapAgentError):
            raise exc_cls("synthetic")
