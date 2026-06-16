"""cap-terminal TmuxSession 包装逻辑单元测试。

对应 spec.md FR-021；tasks.md T042。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from cap_terminal.tmux_session import TmuxSession


@pytest.fixture
def mock_server() -> MagicMock:
    """Mock libtmux.Server，含 session/window/pane 链。"""
    server = MagicMock(name="libtmux.Server")
    session = MagicMock(name="session")
    window = MagicMock(name="window")
    pane = MagicMock(name="pane")

    server.sessions = []
    server.new_session.return_value = session
    session.name = "sandbox"
    # windows 须支持 len()、迭代与 for-in
    session.windows = [window]
    session.active_pane = pane
    window.attached_pane = pane
    window.active_pane = pane
    window.panes = [pane]
    window.split_window.return_value = pane

    # send_keys + capture_pane 默认模拟「成功执行 echo hello」
    pane.send_keys.return_value = None
    _set_capture_sequence(pane, command="echo hello", stdout=["hello"], exit_code=0)
    pane.current_field = None

    return server


def _set_capture_sequence(
    pane: MagicMock,
    command: str,
    stdout: list[str],
    exit_code: int,
) -> None:
    """让 capture_pane 在第二次调用后返回带 marker 的内容（命令完成）。

    模拟 send_keys 注入命令 + marker echo 后，下次 capture_pane 能看到 marker。
    """
    marker_holder: dict[str, str | None] = {"marker": None}

    def fake_send_keys(text: str, enter: bool = True) -> None:
        # 第一次 send_keys 是命令；第二次是 echo marker:$?
        if text.startswith("echo __CMD_END_"):
            marker_holder["marker"] = text.split()[1].rstrip(":$?")
            return

    def fake_capture_pane() -> list[str]:
        marker = marker_holder["marker"]
        if marker is None:
            # 命令尚未派发，返回空 prompt
            return ["$ "]
        # 命令已派发，返回 stdout + marker 行
        lines = ["", f"$ {command}"]
        lines.extend(stdout)
        lines.append(f"{marker}:{exit_code}")
        lines.append("$ ")
        return lines

    pane.send_keys.side_effect = fake_send_keys
    pane.capture_pane.side_effect = fake_capture_pane


def test_run_creates_session_if_absent(mock_server: MagicMock) -> None:
    """首次调用时自动创建 session sandbox。"""
    mock_server.sessions = []  # 无现有 session
    with patch("cap_terminal.tmux_session.libtmux.Server", return_value=mock_server):
        session = TmuxSession(session_name="sandbox", socket_path="/tmp/tmux-test")
        result = session.run("echo hello", timeout_s=5)

    mock_server.new_session.assert_called_once_with(
        session_name="sandbox", attach=False
    )
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]


def test_run_reuses_existing_session(mock_server: MagicMock) -> None:
    """session 已存在时不重建。"""
    existing_session = MagicMock(name="existing-session")
    existing_session.name = "sandbox"
    existing_session.active_pane = mock_server.new_session.return_value.active_pane
    mock_server.sessions = [existing_session]

    with patch("cap_terminal.tmux_session.libtmux.Server", return_value=mock_server):
        session = TmuxSession(session_name="sandbox", socket_path="/tmp/tmux-test")
        session.run("true", timeout_s=1)

    mock_server.new_session.assert_not_called()


def test_run_returns_exit_code_zero_for_success(mock_server: MagicMock) -> None:
    """成功命令 exit_code=0。"""
    with patch("cap_terminal.tmux_session.libtmux.Server", return_value=mock_server):
        session = TmuxSession(session_name="sandbox", socket_path="/tmp/tmux-test")
        result = session.run("true", timeout_s=5)

    assert result["exit_code"] == 0


def test_run_returns_nonzero_for_failure(mock_server: MagicMock) -> None:
    """失败命令 exit_code 非 0。"""
    pane = mock_server.new_session.return_value.active_pane
    _set_capture_sequence(pane, command="false", stdout=[], exit_code=1)
    with patch("cap_terminal.tmux_session.libtmux.Server", return_value=mock_server):
        session = TmuxSession(session_name="sandbox", socket_path="/tmp/tmux-test")
        result = session.run("false", timeout_s=5)

    assert result["exit_code"] != 0


def test_run_result_has_duration_ms(mock_server: MagicMock) -> None:
    """返回值包含 duration_ms（int 类型）。"""
    with patch("cap_terminal.tmux_session.libtmux.Server", return_value=mock_server):
        session = TmuxSession(session_name="sandbox", socket_path="/tmp/tmux-test")
        result = session.run("echo", timeout_s=5)

    assert isinstance(result["duration_ms"], int)
    assert result["duration_ms"] >= 0


def test_run_result_fields_complete(mock_server: MagicMock) -> None:
    """返回值含全部 4 个字段。"""
    with patch("cap_terminal.tmux_session.libtmux.Server", return_value=mock_server):
        session = TmuxSession(session_name="sandbox", socket_path="/tmp/tmux-test")
        result = session.run("echo hi", timeout_s=5)

    assert set(result.keys()) == {"exit_code", "stdout", "stderr", "duration_ms"}


def test_run_timeout_returns_negative_exit_code(mock_server: MagicMock) -> None:
    """超时返回 exit_code=-1 + stderr 提示。

    使用 capture_pane 永远不返回 marker，模拟命令卡死。
    """
    pane = mock_server.new_session.return_value.active_pane
    # 还原为简单 return_value（不返回 marker）
    pane.send_keys.side_effect = None
    pane.capture_pane.side_effect = None
    pane.capture_pane.return_value = ["$ sleep 999", "$ "]
    with patch("cap_terminal.tmux_session.libtmux.Server", return_value=mock_server):
        session = TmuxSession(session_name="sandbox", socket_path="/tmp/tmux-test")
        result = session.run("sleep 999", timeout_s=1)

    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"].lower()
    # Ctrl-C 应被发送
    pane.send_keys.assert_any_call("C-c", enter=False)


def test_status_returns_alive_info(mock_server: MagicMock) -> None:
    """status() 返回 session 名/windows/panes/alive 字段。"""
    with patch("cap_terminal.tmux_session.libtmux.Server", return_value=mock_server):
        session = TmuxSession(session_name="sandbox", socket_path="/tmp/tmux-test")
        info = session.status()

    assert info["session_name"] == "sandbox"
    assert info["alive"] is True
    assert isinstance(info["windows"], int)
    assert isinstance(info["panes"], int)


def test_status_returns_dead_when_server_unreachable(
    mock_server: MagicMock,
) -> None:
    """tmux server 不可达时 status() alive=False。"""
    # 让 self.session 触发异常（active_pane 抛错代表 server 不可达）
    session_mock = mock_server.new_session.return_value
    # windows 访问抛错；status() 中 len(session.windows) 进 except
    windows_mock = MagicMock(name="windows")
    type(session_mock).windows = property(
        lambda _: (_ for _ in ()).throw(RuntimeError("server down"))
    )
    with patch("cap_terminal.tmux_session.libtmux.Server", return_value=mock_server):
        session = TmuxSession(session_name="sandbox", socket_path="/tmp/tmux-test")
        info = session.status()

    assert info["alive"] is False
    assert info["windows"] == 0
    # 清理 type 修改，避免污染后续测试
    del type(session_mock).windows
