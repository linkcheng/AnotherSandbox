"""cap-agent /gui/screenshot 路由单元测试。

对应 spec.md FR-018；tasks.md T074。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


def test_screenshot_returns_png_content_type(client: TestClient) -> None:
    """GET /gui/screenshot 返回 image/png。"""
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 2048  # >1KB
    with patch("cap_agent.routers.gui.gui_backend") as mock_backend:
        mock_backend.screenshot = AsyncMock(return_value=fake_png)
        response = client.get("/gui/screenshot")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 1024


def test_screenshot_failure_returns_500(client: TestClient) -> None:
    """pyautogui 失败时 500。"""
    with patch("cap_agent.routers.gui.gui_backend") as mock_backend:
        mock_backend.screenshot = AsyncMock(side_effect=Exception("DISPLAY not set"))
        response = client.get("/gui/screenshot")

    assert response.status_code == 500


def test_gui_actions_dispatches_to_backend(client: TestClient) -> None:
    """POST /gui/actions 根据 action_type 调用 backend.execute。"""
    with patch("cap_agent.routers.gui.gui_backend") as mock_backend:
        mock_backend.execute = AsyncMock(return_value={"ok": True})
        response = client.post(
            "/gui/actions",
            json={"action_type": "click", "x": 100, "y": 200},
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    mock_backend.execute.assert_called_once()


def test_gui_actions_unknown_type_returns_422(client: TestClient) -> None:
    """未知 action_type 返回 422。"""
    response = client.post(
        "/gui/actions",
        json={"action_type": "unknown_xyz", "x": 1},
    )
    assert response.status_code == 422


def test_gui_actions_typing_dispatches(client: TestClient) -> None:
    """typing action 转发到 backend.execute。"""
    with patch("cap_agent.routers.gui.gui_backend") as mock_backend:
        mock_backend.execute = AsyncMock(return_value={"ok": True})
        response = client.post(
            "/gui/actions",
            json={"action_type": "typing", "text": "abc"},
        )

    assert response.status_code == 200


def test_gui_actions_failure_returns_500(client: TestClient) -> None:
    """backend.execute 异常时 500。"""
    with patch("cap_agent.routers.gui.gui_backend") as mock_backend:
        mock_backend.execute = AsyncMock(side_effect=Exception("pyautogui error"))
        response = client.post(
            "/gui/actions",
            json={"action_type": "click", "x": 1, "y": 1},
        )
    assert response.status_code == 500
