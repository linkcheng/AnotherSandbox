"""cap-agent 16 种 GUI Action pydantic discriminated union 测试。

对应 spec.md FR-018；tasks.md T073；data-model.md。
"""
from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from cap_agent.models.actions import (
    ClickAction,
    GUIAction,
    HotkeyAction,
    TypingAction,
)


def test_click_action_validates() -> None:
    """click 动作可正确校验，button 默认 left。"""
    action = ClickAction(action_type="click", x=100, y=200)
    assert action.action_type == "click"
    assert action.x == 100
    assert action.button == "left"


def test_typing_action_validates() -> None:
    """typing 动作校验 text 字段。"""
    action = TypingAction(action_type="typing", text="hello")
    assert action.text == "hello"


def test_gui_action_discriminates_by_action_type() -> None:
    """TypeAdapter[GUIAction] 根据 action_type 路由到正确子类。"""
    adapter = TypeAdapter(GUIAction)
    action = adapter.validate_python({"action_type": "click", "x": 1, "y": 2})
    assert isinstance(action, ClickAction)


def test_unknown_action_type_rejected() -> None:
    """未知 action_type 触发 ValidationError。"""
    adapter = TypeAdapter(GUIAction)
    with pytest.raises(ValidationError):
        adapter.validate_python({"action_type": "unknown_action", "x": 1})


def test_all_16_action_types_present() -> None:
    """16 种 action_type 全部可解析。"""
    adapter = TypeAdapter(GUIAction)
    expected = {
        "click", "dbl_click", "right_click", "move_to", "move_rel",
        "scroll", "drag", "typing", "hotkey", "key_down", "key_up",
        "screenshot", "wait", "locate", "wait_for", "resize",
    }
    samples = {
        "click": {"x": 0, "y": 0},
        "dbl_click": {"x": 0, "y": 0},
        "right_click": {"x": 0, "y": 0},
        "move_to": {"x": 0, "y": 0},
        "move_rel": {"dx": 0, "dy": 0},
        "scroll": {"amount": 1},
        "drag": {"x": 0, "y": 0},
        "typing": {"text": "x"},
        "hotkey": {"keys": ["ctrl"]},
        "key_down": {"key": "ctrl"},
        "key_up": {"key": "ctrl"},
        "screenshot": {},
        "wait": {"seconds": 0.1},
        "locate": {"image_path": "/x.png"},
        "wait_for": {"image_path": "/x.png"},
        "resize": {"width": 800, "height": 600},
    }
    for action_type in expected:
        payload = {"action_type": action_type, **samples[action_type]}
        action = adapter.validate_python(payload)
        assert action.action_type == action_type


def test_click_missing_x_rejected() -> None:
    """click 缺 x 字段触发 ValidationError。"""
    with pytest.raises(ValidationError):
        ClickAction(action_type="click", y=0)


def test_typing_missing_text_rejected() -> None:
    """typing 缺 text 字段触发 ValidationError。"""
    with pytest.raises(ValidationError):
        TypingAction(action_type="typing")


def test_hotkey_keys_is_list_of_str() -> None:
    """hotkey.keys 是 list[str]。"""
    action = HotkeyAction(action_type="hotkey", keys=["ctrl", "shift", "esc"])
    assert len(action.keys) == 3
