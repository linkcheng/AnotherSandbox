"""T040: compose_runner 测试（mock create_subprocess_exec）。research.md R7。"""
from unittest.mock import AsyncMock, patch

import pytest

from orchestrator.services import compose_runner


class _FakeProc:
    def __init__(self, rc: int, stderr: bytes = b""):
        self.returncode = rc
        self._stderr = stderr

    async def communicate(self):
        return (b"", self._stderr)


@pytest.mark.asyncio
async def test_up_invokes_compose_non_shell():
    captured: dict = {}

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        captured["env"] = kwargs.get("env", {})
        captured["cwd"] = kwargs.get("cwd")
        return _FakeProc(0)

    env = compose_runner.workspace_env("ws-alice", 8101, "wid", "/v", "http://h:8000", "orchestrator", "fail-closed")
    with patch("orchestrator.services.compose_runner.asyncio.create_subprocess_exec", new=fake_exec):
        result = await compose_runner.up("ws-alice", env, "/repo")
    assert result.success is True
    assert captured["args"][0] == "docker"
    assert captured["args"][1] == "compose"
    assert "-p" in captured["args"] and "ws-alice" in captured["args"]
    assert "up" in captured["args"] and "--wait" in captured["args"]
    assert captured["env"]["WORKSPACE_SLUG"] == "ws-alice"
    assert captured["env"]["WS_NGINX_PORT"] == "8101"
    assert captured["cwd"] == "/repo"


@pytest.mark.asyncio
async def test_up_failure_returncode_mapped():
    with patch(
        "orchestrator.services.compose_runner.asyncio.create_subprocess_exec",
        new=AsyncMock(return_value=_FakeProc(1, b"port already allocated")),
    ):
        result = await compose_runner.up("ws-x", {}, "/repo")
    assert result.success is False
    assert result.returncode == 1
    assert "port already allocated" in result.stderr


@pytest.mark.asyncio
async def test_down_with_and_without_volumes():
    calls: list = []

    async def fake_exec(*args, **kwargs):
        calls.append(args)
        return _FakeProc(0)

    with patch("orchestrator.services.compose_runner.asyncio.create_subprocess_exec", new=fake_exec):
        await compose_runner.down("ws-x", {}, "/repo", volumes=True)
        await compose_runner.down("ws-y", {}, "/repo", volumes=False)
    assert "-v" in calls[0]   # volumes=True
    assert "-v" not in calls[1]  # volumes=False
