"""libtmux 包装：固定 session sandbox + window，懒初始化 + respawn。

设计原则三：Human 与 Agent 共享 PTY/cwd（spec.md FR-021；research.md R3）。
"""
from __future__ import annotations

import time
from typing import Any

import libtmux


class TmuxSession:
    """封装固定 session 名的 libtmux 操作。

    所有命令在固定 window 的 attached pane 内执行，确保 human 与 agent
    共享 cwd 与历史。

    Attributes:
        _session_name: 固定 session 名（默认 sandbox）。
        _socket_path: tmux server unix socket 路径；None 时使用默认 socket。
    """

    def __init__(
        self,
        session_name: str = "sandbox",
        socket_path: str | None = None,
    ) -> None:
        """初始化包装器，延迟创建 server/session。

        Args:
            session_name: 固定 tmux session 名。
            socket_path: tmux server socket路径；None 使用默认。
        """
        self._session_name = session_name
        self._socket_path = socket_path
        self._server: libtmux.Server | None = None
        self._session: libtmux.Session | None = None

    @property
    def server(self) -> libtmux.Server:
        """懒初始化 libtmux.Server。"""
        if self._server is None:
            kwargs: dict[str, Any] = {}
            if self._socket_path is not None:
                kwargs["socket_path"] = self._socket_path
            self._server = libtmux.Server(**kwargs)
        return self._server

    @property
    def session(self) -> libtmux.Session:
        """获取或创建 session sandbox。"""
        if self._session is None or not self._is_session_alive():
            self._session = self._get_or_create_session()
        return self._session

    def _is_session_alive(self) -> bool:
        """检查已缓存的 session 是否仍存活。"""
        if self._session is None:
            return False
        try:
            # 访问属性会触发 libtmux 内部 server 查询
            _ = self._session.id
            return True
        except Exception:
            # 缓存失效，下次访问会重建
            self._session = None
            return False

    def _get_or_create_session(self) -> libtmux.Session:
        """复用现有 session 或创建新的。"""
        try:
            for s in self.server.sessions:
                if s.name == self._session_name:
                    return s
        except libtmux.libtmux_exc.LibTmuxException:
            # server 未启动，new_session 会自动 spawn
            pass

        return self.server.new_session(
            session_name=self._session_name,
            attach=False,
        )

    def run(self, command: str, timeout_s: int = 30) -> dict[str, Any]:
        """在 session 的 attached pane 执行命令，返回结构化结果。

        Args:
            command: 要执行的 shell 命令。
            timeout_s: 超时秒数，默认 30。

        Returns:
            {exit_code, stdout, stderr, duration_ms}。
        """
        start = time.monotonic()
        pane = self.session.active_pane

        # 通过 marker 行识别命令完成并解析退出码
        end_marker = f"__CMD_END_{int(start * 1000)}__"
        pane.send_keys(command)
        pane.send_keys(f"echo {end_marker}:$?")

        deadline = start + timeout_s
        captured: list[str] = []
        exit_code = 0

        while time.monotonic() < deadline:
            captured = pane.capture_pane() or []
            for line in captured:
                if end_marker in line:
                    try:
                        exit_code = int(line.split(":")[-1].strip())
                    except (ValueError, IndexError):
                        exit_code = 0
                    duration_ms = int((time.monotonic() - start) * 1000)
                    stdout, stderr = self._split_output(
                        captured, command, end_marker
                    )
                    return {
                        "exit_code": exit_code,
                        "stdout": stdout,
                        "stderr": stderr,
                        "duration_ms": duration_ms,
                    }
            time.sleep(0.05)

        # 超时：发送 Ctrl-C 中断
        pane.send_keys("C-c", enter=False)
        time.sleep(0.2)
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout_s}s\n",
            "duration_ms": duration_ms,
        }

    @staticmethod
    def _split_output(
        captured: list[str],
        command: str,
        end_marker: str,
    ) -> tuple[str, str]:
        """从 capture_pane 内容中分离 stdout 与 stderr。

        P1 简化：tmux pane 不区分 stdout/stderr（共享 PTY），
        将所有非命令非 marker 行作为 stdout，stderr 留空（契约规定 P1 不分离）。
        """
        stdout_lines: list[str] = []
        skip_command_echo = True
        first_token = command.split()[0] if command.split() else ""

        for line in captured:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped == "$":
                continue
            if end_marker in line:
                break
            if skip_command_echo and first_token and first_token in stripped:
                skip_command_echo = False
                continue
            stdout_lines.append(line)

        return "\n".join(stdout_lines) + ("\n" if stdout_lines else ""), ""

    def status(self) -> dict[str, Any]:
        """返回 session 元信息。"""
        try:
            session = self.session
            windows = len(session.windows)
            panes = sum(len(w.panes) for w in session.windows)
            return {
                "session_name": session.name,
                "windows": windows,
                "panes": panes,
                "alive": True,
            }
        except Exception:
            return {
                "session_name": self._session_name,
                "windows": 0,
                "panes": 0,
                "alive": False,
            }


# 模块级单例，FastAPI 路由共享
tmux_session = TmuxSession(session_name="sandbox")
