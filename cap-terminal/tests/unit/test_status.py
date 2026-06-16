"""cap-terminal status 与 health 端点单元测试。

对应 spec.md FR-020；tasks.md T043。
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """GET /api/v1/health 返回 ok（已有契约）。"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_terminal_status_returns_session_info(client: TestClient) -> None:
    """GET /api/v1/terminal/status 返回 tmux session 元信息。"""
    fake_session_info = {
        "session_name": "sandbox",
        "windows": 1,
        "panes": 1,
        "alive": True,
    }
    with patch("cap_terminal.routers.status.tmux_session") as mock_session:
        mock_session.status.return_value = fake_session_info
        response = client.get("/api/v1/terminal/status")

    assert response.status_code == 200
    body = response.json()
    assert body["session_name"] == "sandbox"
    assert body["alive"] is True
    assert isinstance(body["windows"], int)


def test_terminal_status_when_tmux_down(client: TestClient) -> None:
    """tmux server 不可达时 alive=False。"""
    with patch("cap_terminal.routers.status.tmux_session") as mock_session:
        mock_session.status.return_value = {
            "session_name": "sandbox",
            "windows": 0,
            "panes": 0,
            "alive": False,
        }
        response = client.get("/api/v1/terminal/status")

    assert response.status_code == 200
    assert response.json()["alive"] is False
