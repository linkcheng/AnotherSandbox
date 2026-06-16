"""cap-terminal POST /api/v1/exec 单元测试。

对应 spec.md FR-020；tasks.md T041；contracts/cap-terminal-api.md。
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_exec_echo_success(client: TestClient) -> None:
    """echo hello 返回 exit_code=0 + stdout=hello\n。"""
    fake_result = {
        "exit_code": 0,
        "stdout": "hello\n",
        "stderr": "",
        "duration_ms": 12,
    }
    with patch("cap_terminal.routers.exec.tmux_session") as mock_session:
        mock_session.run.return_value = fake_result
        response = client.post("/api/v1/exec", json={"command": "echo hello"})

    assert response.status_code == 200
    body = response.json()
    assert body["exit_code"] == 0
    assert body["stdout"] == "hello\n"
    assert body["stderr"] == ""
    assert isinstance(body["duration_ms"], int)


def test_exec_command_failure(client: TestClient) -> None:
    """非零退出码原样返回（exit_code=1）。"""
    fake_result = {
        "exit_code": 1,
        "stdout": "",
        "stderr": "No such file or directory\n",
        "duration_ms": 5,
    }
    with patch("cap_terminal.routers.exec.tmux_session") as mock_session:
        mock_session.run.return_value = fake_result
        response = client.post("/api/v1/exec", json={"command": "ls /nonexistent"})

    assert response.status_code == 200
    assert response.json()["exit_code"] == 1
    assert "No such file" in response.json()["stderr"]


def test_exec_timeout(client: TestClient) -> None:
    """超时返回 exit_code=-1 + stderr 提示。"""
    fake_result = {
        "exit_code": -1,
        "stdout": "",
        "stderr": "Command timed out after 1s\n",
        "duration_ms": 1000,
    }
    with patch("cap_terminal.routers.exec.tmux_session") as mock_session:
        mock_session.run.return_value = fake_result
        response = client.post(
            "/api/v1/exec",
            json={"command": "sleep 100", "timeout_s": 1},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["exit_code"] == -1
    assert "timed out" in body["stderr"].lower()
    mock_session.run.assert_called_once_with("sleep 100", timeout_s=1)


def test_exec_empty_command_rejected(client: TestClient) -> None:
    """空命令返回 422（pydantic 校验）。"""
    response = client.post("/api/v1/exec", json={"command": ""})
    assert response.status_code == 422


def test_exec_missing_command_rejected(client: TestClient) -> None:
    """缺 command 字段返回 422。"""
    response = client.post("/api/v1/exec", json={})
    assert response.status_code == 422


def test_exec_default_timeout_30s(client: TestClient) -> None:
    """未指定 timeout_s 时默认 30s。"""
    with patch("cap_terminal.routers.exec.tmux_session") as mock_session:
        mock_session.run.return_value = {
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "duration_ms": 1,
        }
        client.post("/api/v1/exec", json={"command": "true"})

    mock_session.run.assert_called_once_with("true", timeout_s=30)
