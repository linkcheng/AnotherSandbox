"""cap-agent GUIBackend 单元测试。

直接测 GUIBackend 类，通过 sys.modules 注入 mock pyautogui/pyperclip，
覆盖 _ensure_pa、screenshot、_execute_sync 的各 action_type 分支。
对应 spec.md FR-018、FR-029。
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_pyautogui() -> types.ModuleType:
    """注入 mock pyautogui 模块到 sys.modules。"""
    mock = types.ModuleType("pyautogui")
    mock.FAILSAFE = True
    mock.PAUSE = 0.1
    mock.click = MagicMock()
    mock.doubleClick = MagicMock()
    mock.rightClick = MagicMock()
    mock.moveTo = MagicMock()
    mock.moveRel = MagicMock()
    mock.scroll = MagicMock()
    mock.dragTo = MagicMock()
    mock.typewrite = MagicMock()
    mock.hotkey = MagicMock()
    mock.keyDown = MagicMock()
    mock.keyUp = MagicMock()
    mock.locateOnScreen = MagicMock(return_value=None)
    mock.screenshot = MagicMock(return_value=MagicMock(save=MagicMock()))
    sys.modules["pyautogui"] = mock
    yield mock
    sys.modules.pop("pyautogui", None)


@pytest.fixture
def mock_pyperclip() -> types.ModuleType:
    """注入 mock pyperclip 模块。"""
    mock = types.ModuleType("pyperclip")
    mock.copy = MagicMock()
    sys.modules["pyperclip"] = mock
    yield mock
    sys.modules.pop("pyperclip", None)


@pytest.fixture
def backend(mock_pyautogui, mock_pyperclip):
    """每个 test 独立 GUIBackend 实例。"""
    from cap_agent.services.gui_backend import GUIBackend
    return GUIBackend()


@pytest.mark.asyncio
async def test_screenshot_returns_png_bytes(backend, mock_pyautogui) -> None:
    """screenshot 返回 PNG bytes。"""
    from PIL import Image
    img = Image.new("RGB", (10, 10), color="red")
    mock_pyautogui.screenshot.return_value = img

    result = await backend.screenshot()
    assert isinstance(result, bytes)
    assert result.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_screenshot_failure_propagates(backend, mock_pyautogui) -> None:
    """pyautogui.screenshot 抛异常时传播。"""
    mock_pyautogui.screenshot.side_effect = RuntimeError("no DISPLAY")
    with pytest.raises(RuntimeError, match="no DISPLAY"):
        await backend.screenshot()


@pytest.mark.asyncio
async def test_ensure_pa_sets_failsafe_and_pause(backend, mock_pyautogui) -> None:
    """懒加载时设置 FAILSAFE=False、PAUSE=0。"""
    backend._ensure_pa()
    assert mock_pyautogui.FAILSAFE is False
    assert mock_pyautogui.PAUSE == 0


@pytest.mark.asyncio
async def test_execute_click_calls_pyautogui(backend, mock_pyautogui) -> None:
    """click action 调用 pyautogui.click。"""
    from cap_agent.models.actions import ClickAction
    action = ClickAction(action_type="click", x=10, y=20, button="right")
    result = await backend.execute(action)
    mock_pyautogui.click.assert_called_once_with(10, 20, button="right")
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_execute_dbl_click(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import DblClickAction
    await backend.execute(DblClickAction(action_type="dbl_click", x=1, y=2))
    mock_pyautogui.doubleClick.assert_called_once_with(1, 2)


@pytest.mark.asyncio
async def test_execute_right_click(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import RightClickAction
    await backend.execute(RightClickAction(action_type="right_click", x=1, y=2))
    mock_pyautogui.rightClick.assert_called_once_with(1, 2)


@pytest.mark.asyncio
async def test_execute_move_to(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import MoveToAction
    await backend.execute(MoveToAction(action_type="move_to", x=5, y=6))
    mock_pyautogui.moveTo.assert_called_once_with(5, 6)


@pytest.mark.asyncio
async def test_execute_move_rel(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import MoveRelAction
    await backend.execute(MoveRelAction(action_type="move_rel", dx=-1, dy=1))
    mock_pyautogui.moveRel.assert_called_once_with(-1, 1)


@pytest.mark.asyncio
async def test_execute_scroll(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import ScrollAction
    await backend.execute(ScrollAction(action_type="scroll", amount=3, x=10, y=20))
    mock_pyautogui.scroll.assert_called_once_with(3, x=10, y=20)


@pytest.mark.asyncio
async def test_execute_drag(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import DragAction
    await backend.execute(DragAction(action_type="drag", x=100, y=200, duration=1.0))
    mock_pyautogui.dragTo.assert_called_once_with(100, 200, duration=1.0)


@pytest.mark.asyncio
async def test_execute_typing_ascii(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import TypingAction
    await backend.execute(TypingAction(action_type="typing", text="hello"))
    mock_pyautogui.typewrite.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_execute_typing_unicode_uses_clipboard(backend, mock_pyautogui, mock_pyperclip) -> None:
    """非 ASCII 文本走剪贴板（ctrl+v）。"""
    from cap_agent.models.actions import TypingAction
    await backend.execute(TypingAction(action_type="typing", text="你好"))
    mock_pyperclip.copy.assert_called_once_with("你好")
    mock_pyautogui.hotkey.assert_called_once_with("ctrl", "v")


@pytest.mark.asyncio
async def test_execute_hotkey(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import HotkeyAction
    await backend.execute(HotkeyAction(action_type="hotkey", keys=["ctrl", "c"]))
    mock_pyautogui.hotkey.assert_called_once_with("ctrl", "c")


@pytest.mark.asyncio
async def test_execute_key_down_and_up(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import KeyDownAction, KeyUpAction
    await backend.execute(KeyDownAction(action_type="key_down", key="shift"))
    await backend.execute(KeyUpAction(action_type="key_up", key="shift"))
    mock_pyautogui.keyDown.assert_called_once_with("shift")
    mock_pyautogui.keyUp.assert_called_once_with("shift")


@pytest.mark.asyncio
async def test_execute_screenshot_action_noop(backend) -> None:
    from cap_agent.models.actions import ScreenshotAction
    result = await backend.execute(ScreenshotAction(action_type="screenshot"))
    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_execute_wait_sleeps(backend, monkeypatch) -> None:
    from cap_agent.models.actions import WaitAction
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    await backend.execute(WaitAction(action_type="wait", seconds=0.5))
    assert 0.5 in slept


@pytest.mark.asyncio
async def test_execute_locate_found_returns_box(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import LocateAction
    mock_pyautogui.locateOnScreen.return_value = (10, 20, 30, 40)  # Box tuple
    result = await backend.execute(
        LocateAction(action_type="locate", image_path="/x.png", confidence=0.8)
    )
    assert result["ok"] is True
    assert result["found"] is True
    assert result["box"] == [10, 20, 30, 40]


@pytest.mark.asyncio
async def test_execute_locate_not_found(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import LocateAction
    mock_pyautogui.locateOnScreen.return_value = None
    result = await backend.execute(
        LocateAction(action_type="locate", image_path="/x.png")
    )
    assert result["found"] is False


@pytest.mark.asyncio
async def test_execute_wait_for_handles_exception(backend, mock_pyautogui) -> None:
    from cap_agent.models.actions import WaitForAction
    mock_pyautogui.locateOnScreen.side_effect = Exception("image not readable")
    result = await backend.execute(
        WaitForAction(action_type="wait_for", image_path="/missing.png")
    )
    assert result["ok"] is False
    assert "image not readable" in result["error"]


@pytest.mark.asyncio
async def test_execute_resize_returns_p1_placeholder(backend) -> None:
    from cap_agent.models.actions import ResizeAction
    result = await backend.execute(
        ResizeAction(action_type="resize", width=1024, height=768)
    )
    assert result["ok"] is False
    assert "P1" in result["error"]
